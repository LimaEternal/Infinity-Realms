import os
import re


def remove_emojis(data):
    emoj = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U00002500-\U00002bef"  # chinese char
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2b55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        re.UNICODE,
    )
    return re.sub(emoj, "", data)


def process_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        # Skip binary files
        return
    new_content = remove_emojis(content)
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Processed: {filepath}")
    else:
        print(f"No emojis found: {filepath}")


def main():
    root = os.getcwd()
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip certain directories
        if ".git" in dirpath.split(os.sep) or "__pycache__" in dirpath.split(os.sep):
            continue
        for f in filenames:
            filepath = os.path.join(dirpath, f)
            process_file(filepath)


if __name__ == "__main__":
    main()
