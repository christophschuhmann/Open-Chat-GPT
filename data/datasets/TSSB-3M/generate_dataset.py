"""Convert the source TSSB-3M  dataset to instruction data
"""

import json
import re
from os.path import join

from tqdm import tqdm
import secrets

INSTRUCTIONS_LIST = [
    "Find the bug in the following code:",
    "Identify the error in the code snippet provided:",
    "Spot the issue within the given code segment:",
    "Locate the problem in the code example below:",
    "Uncover the malfunction in the following piece of code:",
    "Detect the flaw in the code provided:",
    "Pinpoint the glitch in the code sample below:",
    "Search for the anomaly in the given code:",
    "Determine the defect within the following code:",
    "Discover the fault in the code segment provided:",
    "Trace the irregularity in the code example below:",
    "Please locate the error in the code provided.",
    "Can you identify the mistake in this code?",
    "There seems to be a problem with this code. Can you find it?",
    "Please investigate the code and locate the bug.",
    "Please examine the code and find the error.",
    "Can you pinpoint the issue with this code?",
    "Please review the code and identify the bug.",
    "Can you detect the problem with this code?",
    "Please analyze the code and find the mistake.",
    "Can you spot the bug in the code provided?",
]


RESPONSE_PREFIX_WORDS = [
    "The fix of the bug can be laid out as",
    "The resolution of the error can be portrayed like so",
    "The solution for the flaw can be summarized as such",
    "The remedy of the mistake can be captured in this way",
    "The correction of the fault can be depicted like this",
    "The patch for the glitch can be articulated as",
    "The workaround of the defect can be conveyed in this manner",
    "The troubleshooting of the issue can be explained like this",
    "The adjustment to the anomaly can be illustrated as follows",
    "The modification for the irregularity can be exemplified like this",
]


def gen_instruction():
    idx = secrets.SystemRandom().randint(0, len(INSTRUCTIONS_LIST) - 1)
    return INSTRUCTIONS_LIST[idx]


def gen_response_prefix():
    idx = secrets.SystemRandom().randint(0, len(RESPONSE_PREFIX_WORDS) - 1)
    return RESPONSE_PREFIX_WORDS[idx]


TEMPLATE = """User: {}
{}
Reply: The fixed code is:
```
{}
```
"""


# template for pretty output(multiple lines with `User:` & `Reply`)
TEMPLATE_COMMIT_MSG = """User: {}
{}
Reply: {}:
{}
The fixed code is:
```
{}
```
"""

INSTRUCTON_TEMPLATE = """{}
{}
"""


# template for json output(value)

RESPONSE_TEMPLATE = """The fixed code is:
```
{}
```
"""

RESPONSE_TEMPLATE_COMMIT_MSG = """{}:
{}

The fixed code is:
```
{}
```
"""


def remove_starting_plus_minus(text):
    if text.startswith("+") or text.startswith("-"):
        return text[1:]
    else:
        return text


def remove_extraneous_diff_info(text):
    pattern = "@@.*@@"
    return re.sub(pattern, "", text)


def clean(text):
    return remove_extraneous_diff_info(remove_starting_plus_minus(text))


def clean_PII(text):
    # Remove sign-off messege generated by `git commit --signoff`, eg. "Signed-off-by: user_name <xx@yy.zz.com>"
    signoff_index = text.rfind("\n\nSigned-off-by:")
    if signoff_index != -1:
        # Remove the sign-off string from the commit message
        text = text[:signoff_index]

    # remove email
    email_pattern = r"[a-zA-Z0-9._%+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}"
    clean_text = re.sub(email_pattern, "", text)
    return clean_text


INVALID_COMMIT_MESSAGES = set([line.strip().split("\t")[0] for line in open("invalid_commit_messages.tsv").readlines()])


def is_invaid_commit_msg(text):
    """commit message that is incomplete, eg. "fix bug", "hotfix" """
    return text.strip() in INVALID_COMMIT_MESSAGES


def clean_commit_msg(text):
    """
    # 1. remove issue id , eg. msg: "rename (hetr_passes -> passes) #1195" -> "rename (hetr_passes -> passes)"
    # 2. remove `fix` prefix:
    some typical cases:
    ## eg. [fix] 拼写错误 -> 拼写错误
    ## eg. [FIX] purchase_indonesia : AttributeError 'NoneType' object has no attribute 'id' ->  AttributeError 'NoneType' object has no attribute 'id'
    ## "fix force insert error refs #2" -> "fix force insert error"
    ## "Fix namespace of RPCError Fixes #76" ->  "Fix namespace of RPCError"
    ## "fix a minor bug in survey_spec password field handling see: #5477" -> "fix a minor bug in survey_spec password field handling"
    ## issue #973 -> ""
    ## "Fixes #246"  -> ""
    ## "Close #152." -> ""
    ## "wrong learning rate schedule (#2360)"  -> "wrong learning rate schedule"
    """
    # filter commit message that contains PII(github user name/email..)
    text = clean_PII(text)

    # Remove issue id
    pattern = r"\(?#\d{1,6}\)?"
    # re.sub(r"(.+?\s\(.+?\))\s#\d{1,6}", '\\1', text)
    text = re.sub(pattern, "", text)
    # Replace multiple spaces with a single space
    text = re.sub(r"\s+", " ", text).strip()

    # filter commit message that is too short
    if len(text) < 4:
        return None

    if is_invaid_commit_msg(text):
        return None
    return text


def create(input_file, output_file, output_json=True):
    fout = open(output_file, "w")
    with open(input_file) as fin:
        for line in tqdm(fin):
            row = json.loads(line.strip())
            wrong = "\n".join(clean(line) for line in row["diff"].split("\n") if not line.startswith("+"))
            correct = "\n".join(clean(line) for line in row["diff"].split("\n") if not line.startswith("-"))

            instruction = INSTRUCTON_TEMPLATE.format(wrong, correct)

            commit_msg = clean_commit_msg(row["commit_message"]) if "commit_message" in row else None
            if commit_msg:
                # template: (instruct, wrong_code, resposne_prefix, commit_message, correct_code)
                out_str = TEMPLATE_COMMIT_MSG.format(
                    gen_instruction(), wrong, gen_response_prefix(), commit_msg, correct
                )
                response = RESPONSE_TEMPLATE_COMMIT_MSG.format(gen_response_prefix(), commit_msg, correct)
            else:
                # no commit message
                out_str = TEMPLATE.format(gen_instruction(), wrong, correct)
                response = RESPONSE_TEMPLATE.format(correct)

            if output_json:
                row = {
                    "INSTRUCTION": instruction,
                    "RESPONSE": response,
                    "SOURCE": "TSSM-3M",
                    "METADATA": {
                        "project_url": row["project_url"],
                        "file_path": row["file_path"],
                        "commit_sha": row["commit_sha"],
                    },
                }
                out_str = json.dumps(row, ensure_ascii=False)

            print(out_str, file=fout)
        fout.close()


if __name__ == "__main__":
    """
    # get source data from huggingface repository
     !wget https://huggingface.co/datasets/zirui3/TSSB-3M-ext/blob/main/data.jsonl.gz
     !gzip -d data.jsonl.gz
    """

    data_dir = "."
    # source TSSB-3M data
    input_file = join(data_dir, "data.jsonl")

    # output multiple lines
    # output_file = join(data_dir, "instructions_multple_lines.txt")
    # create(input_file, output_file, output_json=False)

    # output jsonl
    output_file = join(data_dir, "instructions.jsonl")
    create(input_file, output_file, output_json=True)
