from oasst_inference_server.models import DbChat, DbMessage, DbUser, DbWorker
from polyfactory.factories.pydantic_factory import ModelFactory


class DbChatFactory(ModelFactory[DbChat]):
    __model__ = DbChat


class DbWorkerFactory(ModelFactory[DbWorker]):
    __model__ = DbWorker


class DbUserFactory(ModelFactory[DbUser]):
    __model__ = DbUser


class DBMessageFactory(ModelFactory[DbMessage]):
    __model__ = DbMessage

    work_parameters = None  # Work params lead to serialization errors if not none
