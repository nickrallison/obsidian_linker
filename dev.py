import os
import sys
import json
import re
import yaml
import functools

from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from pprint import pprint

from main import get_file_dict


def read_json(file_path):
    with open(file_path, 'r', encoding="utf-8") as file:
        return json.load(file)

def open_file(file_path):
    with open(file_path, 'r', encoding="utf-8") as file:
        return file.read()

def serialize_dict_to_json(dict, file_path):
    print(f"Serializing to JSON: {file_path}...")
    with open(file_path, 'w') as file:
        file_str = json.dumps(dict, indent=4)
        file.write(file_str)





if __name__ =="__main__":

    file_paths = read_json("assets/file_paths.json")
    files = read_json("assets/files.json")
    clean_links = read_json("assets/clean_links.json")
    linked_files = read_json("assets/linked_files.json")

    for file_path in file_paths:
        new_body = linked_files[file_path]["frontmatter_string"] + linked_files[file_path]["middle_spaces"] + "".join([string[1] for string in linked_files[file_path]["separated"]])
        with open(file_path, 'w', encoding="utf-8") as file:
            file.write(new_body)

    # pprint(clean_links)
