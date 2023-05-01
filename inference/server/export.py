import argparse
import contextlib
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import TextIO

import sqlalchemy
import sqlmodel
from fastapi.encoders import jsonable_encoder
from oasst_data import (
    ExportMessageEvent,
    ExportMessageEventReport,
    ExportMessageEventScore,
    ExportMessageNode,
    ExportMessageTree,
)
from oasst_inference_server.models import DbChat, DbMessage
from oasst_inference_server.settings import settings
from oasst_shared.utils import Anonymizer
from sqlmodel import Session


@contextlib.contextmanager
def create_session():
    engine = sqlmodel.create_engine(
        settings.database_uri,
        echo=settings.db_echo,
        isolation_level="REPEATABLE READ",
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

    with Session(engine) as db:
        yield db


# see https://stackoverflow.com/questions/17602878/how-to-handle-both-with-open-and-sys-stdout-nicely
@contextlib.contextmanager
def smart_open(filename: str = None) -> TextIO:
    if filename and filename != "-":
        fh = open(filename, "wt", encoding="UTF-8")
    else:
        fh = sys.stdout

    try:
        yield fh
    finally:
        if fh is not sys.stdout:
            fh.close()


def maybe_anonymize(anonymizer: Anonymizer | None, collection: str, key: str) -> str:
    if anonymizer:
        return anonymizer.anonymize(collection, key)
    else:
        return key


def prepare_export_events(
    message: DbMessage,
    anonymizer: Anonymizer | None = None,
) -> dict[str, list[ExportMessageEvent]]:
    export_events: dict[str, list[ExportMessageEvent]] = []

    if message.reports:
        export_events["report"] = [
            ExportMessageEventReport(
                user_id=maybe_anonymize(anonymizer, "user", str(message.chat.user_id)),
                report_type=str(db_report.report_type),
                reason=db_report.reason,
            )
            for db_report in message.reports
        ]

    if message.score:
        export_events["score"] = [
            ExportMessageEventScore(
                user_id=maybe_anonymize(anonymizer, "user", str(message.chat.user_id)),
                score=message.score,
            )
        ]

    return export_events


def prepare_export_message_tree(
    chat: DbChat,
    anonymizer: Anonymizer | None = None,
) -> ExportMessageTree:
    messages: list[DbMessage] = chat.messages

    export_messages: list[ExportMessageNode] = [prepare_export_message_node(m, anonymizer=anonymizer) for m in messages]

    messages_by_parent = defaultdict(list)
    for message in export_messages:
        messages_by_parent[message.parent_id].append(message)

    def assign_replies(node: ExportMessageNode) -> ExportMessageNode:
        node.replies = messages_by_parent[node.message_id]
        for child in node.replies:
            assign_replies(child)
        return node

    prompt = assign_replies(messages_by_parent[None][0])
    return ExportMessageTree(message_tree_id=str(chat.id), tree_state="not_applicable", prompt=prompt)


def prepare_export_message_node(
    message: DbMessage,
    anonymizer: Anonymizer | None = None,
) -> ExportMessageNode:
    if message.worker_config:
        model_name = message.worker_config.model_config.model_id
    else:
        model_name = None

    # Chat prompts are human-written, responses are synthetic
    synthetic = message.role == "assistant"

    events: dict[str, list[ExportMessageEvent]] = prepare_export_events(message)

    message_id = maybe_anonymize(anonymizer, "message", message.id)
    parent_id = maybe_anonymize(anonymizer, "message", message.parent_id)
    user_id = maybe_anonymize(anonymizer, "user", message.chat.user_id)

    return ExportMessageNode(
        message_id=message_id,
        parent_id=parent_id,
        user_id=user_id,
        created_date=message.created_at,
        text=message.content,
        role=message.role,
        synthetic=synthetic,
        model_name=model_name,
        events=events,
    )


def write_messages_to_file(
    file: Path,
    chats: list[DbChat],
    use_compression: bool = True,
    write_trees: bool = True,
    anonymizer: Anonymizer | None = None,
) -> None:
    out_buff: TextIO

    if use_compression:
        if not file:
            raise RuntimeError("File name must be specified when using compression.")
        out_buff = gzip.open(file, "wt", encoding="UTF-8")
    else:
        out_buff = smart_open(file)

    with out_buff as f:
        for c in chats:
            if write_trees:
                export_chat = prepare_export_message_tree(c, anonymizer=anonymizer)
                file_data = jsonable_encoder(export_chat, exclude_none=True)
                json.dump(file_data, f)
                f.write("\n")
            else:
                for m in c.messages:
                    export_message = prepare_export_message_node(m, anonymizer=anonymizer)
                    file_data = jsonable_encoder(export_message, exclude_none=True)
                    json.dump(file_data, f)
                    f.write("\n")


def fetch_eligible_chats(session: Session) -> list[DbChat]:
    """Fetch chats which are not opted out of data collection."""
    query = (
        session.query(DbChat)
        .filter(DbChat.allow_data_use)
        .options(
            sqlalchemy.orm.selectinload(DbChat.messages).selectinload(DbMessage.reports),
        )
    )
    chats: list[DbChat] = query.all()
    return chats


def export_chats(
    session: Session,
    export_path: Path,
    use_compression: bool = True,
    write_trees: bool = True,
    anonymizer_seed: str | None = None,
) -> None:
    eligible_chats: list[DbChat] = fetch_eligible_chats(session)
    anonymizer = Anonymizer(anonymizer_seed) if anonymizer_seed else None

    write_messages_to_file(
        export_path,
        eligible_chats,
        write_trees=write_trees,
        use_compression=use_compression,
        anonymizer=anonymizer,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--export-file",
        type=str,
        help="Name of file to export chats to. If not provided, output will be sent to STDOUT",
    )
    parser.add_argument(
        "--use-compression",
        action="store_false",
        help="Whether to use compression when writing to file. Defaults to True.",
    )
    parser.add_argument(
        "--write-trees",
        action="store_false",
        help="Whether to write chats as trees rather than individual messages. Defaults to True.",
    )
    parser.add_argument(
        "--anonymizer-seed",
        type=int,
        help="Seed for the anonymizer. If not specified, no anonymization will be performed.",
    )
    # TODO: filters: reported, score, user ID, chat ID, etc
    # TODO: date range?
    return parser.parse_args()


def main():
    args = parse_args()

    export_path = Path(args.export_file) if args.export_file else None

    with create_session() as session:
        export_chats(
            session,
            export_path,
            use_compression=args.use_compression,
            write_trees=args.write_trees,
            anonymizer_seed=args.anonymizer_seed,
        )


if __name__ == "__main__":
    main()
