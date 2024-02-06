import functools
import os
import sys
import re
import yaml
import json

from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from pprint import pprint

def open_file(file_path):
    with open(file_path, 'r', encoding="utf-8") as file:
        return file.read()

def serialize_dict_to_json(dict, file_path):
    print(f"Serializing to JSON: {file_path}...")
    with open(file_path, 'w') as file:
        file_str = json.dumps(dict, indent=4)
        file.write(file_str)

def construct_tree_from_aliases(aliases):
    tree = {}
    alias_list = list(aliases.keys())
    for alias in alias_list:
        current_tree = tree
        alias_parts = alias.split(" ")
        while len(alias_parts) > 0:
            part = alias_parts.pop(0)
            if part not in current_tree:
                current_tree[part] = {}
            if len(alias_parts) == 0:
                current_tree[part][""] = aliases[alias]
            current_tree = current_tree[part]

    return tree

def get_links(alias_tree, words, bad_links=[]):
    length = len(words)
    index = 0
    links = []
    while index < length:
        word = words[index][0]
        start_word_index = words[index][1]
        relative_index = 0
        if word.lower() in alias_tree:
            parts = [word.lower()]
            current_tree = alias_tree[word.lower()]
            while word.lower() in current_tree:
                relative_index = relative_index + 1
                word = words[index + relative_index]
                parts.append(word.lower())
                current_tree = current_tree[word.lower()]
            while "" not in current_tree and len(parts) != 0:
                relative_index = relative_index - 1
                word = words[index + relative_index]

                parts.pop()
                current_tree = descend_tree(alias_tree, parts)
            if len(parts) != 0 and current_tree[""][0] not in bad_links:
                link_obj = {}
                link_obj["link"] = current_tree[""][0]
                link_obj["words"] = " ".join(parts)
                link_obj["start_index"] = words[index][1]
                link_obj["end_index"] = words[index + relative_index][1]
                links.append(link_obj)
                index = index + relative_index
        index = index + 1
    return links


def descend_tree(tree, words):
    current_tree = tree
    for word in words:
        current_tree = current_tree[word]
    return current_tree


def clean_file(file):
    file = re.sub(r'```[\s\S]*?```', '', file)
    file = re.sub(r'\$\$[\s\S]*?\$\$', '', file)
    file = re.sub(r'\$[\s\S]*?\$', '', file)
    file = re.sub(r'\[\[[\s\S]*?\]\]', '', file)
    file = re.sub(r'\[[\s\S]*?\]\([\s\S]*?\)', '', file)

    return file


def get_frontmatter(file_paths):
    frontmatter = {}
    for file_path in file_paths:
        file = open_file(file_path)
        reg_search = re.search(r'---(?P<yaml>[\s\S]*?)---\n\s*# (?P<header>.*)\n', file)
        reg_yaml = reg_search.group('yaml')
        reg_frontmatter = yaml.load(reg_yaml, Loader=yaml.FullLoader)
        frontmatter[file_path] = reg_frontmatter
    return frontmatter


def get_aliases(files):
    file_paths = [file for file in files]
    aliases = {}
    for file_path in file_paths:
        file = files[file_path]
        file_frontmatter = file["frontmatter"]
        file_title = os.path.basename(file_path).split(".")[0]
        file_aliases = [file_title.lower()]
        if file_frontmatter['aliases'] is not None:
            if type(file_frontmatter['aliases']) == list:
                for alias in file_frontmatter['aliases']:
                    file_aliases.append(alias)
            elif type(file_frontmatter['aliases']) == str:
                file_aliases.append(file_frontmatter['aliases'])
        for alias in file_aliases:
            if alias in aliases:
                aliases[alias.lower()].append(file_path)
            else:
                aliases[alias.lower()] = [file_path]

    return construct_tree_from_aliases(aliases)


def get_file_dict(file_paths):

    files = {}
    for file_path in file_paths:
        print(file_path)
        file_raw = open_file(file_path)
        search = re.search(
            r'^(?P<frontmatter>---(?P<frontmatter_inner>[\s\S]*?)---)?(?P<middle_spaces>\s*)(?P<body>[\s\S]*)?$',
            file_raw)
        frontmatter_string = search.group('frontmatter')
        frontmatter = yaml.load(search.group('frontmatter_inner'), Loader=yaml.FullLoader)
        middle_spaces = search.group('middle_spaces')
        body_string = search.group('body')

        files[file_path] = {
            "frontmatter_string": frontmatter_string,
            "frontmatter": frontmatter,
            "middle_spaces": middle_spaces,
            "body": body_string
        }

    return files


def separate_string_fsm(content):
    start_state = 0
    latex_inline_state = 1
    latex_block_state = 2
    code_block_state = 3
    link_state = 4
    hyper_link_state = 5
    newline_state = 6
    whitespace_state = 7
    word_state = 8

    latex_inline_regex = r"^\$.+?\$"
    latex_block_regex = r"^\$\$.+?\$\$"
    code_block_regex = r"^```[\s\S]+?```"
    link_regex = r"^\[\[.*?\]\]"
    hyper_link_regex = r"^\[.*?\]\(.*?\)"
    newline_regex = r"^\n"
    whitespace_regex = r"^\s+"
    word_regex = r"^\S+"

    state = start_state
    remaining_content = content

    separated_content = []

    while len(remaining_content) > 0:
        if state == start_state:
            if re.match(latex_inline_regex, remaining_content):
                state = latex_inline_state
            elif re.match(latex_block_regex, remaining_content):
                state = latex_block_state
            elif re.match(code_block_regex, remaining_content):
                state = code_block_state
            elif re.match(link_regex, remaining_content):
                state = link_state
            elif re.match(hyper_link_regex, remaining_content):
                state = hyper_link_state
            elif re.match(newline_regex, remaining_content):
                state = newline_state
            elif re.match(whitespace_regex, remaining_content):
                state = whitespace_state
            elif re.match(word_regex, remaining_content):
                state = word_state
            else:
                print(f"Invalid state: {remaining_content}")
                break
        elif state == latex_inline_state:
            match = re.match(latex_inline_regex, remaining_content)
            separated_content.append(("latex_inline", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state
        elif state == latex_block_state:
            match = re.match(latex_block_regex, remaining_content)
            separated_content.append(("latex_block", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state
        elif state == code_block_state:
            match = re.match(code_block_regex, remaining_content)
            separated_content.append(("code_block", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state
        elif state == link_state:
            match = re.match(link_regex, remaining_content)
            separated_content.append(("link", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state
        elif state == hyper_link_state:
            match = re.match(hyper_link_regex, remaining_content)
            separated_content.append(("hyper_link", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state
        elif state == newline_state:
            match = re.match(newline_regex, remaining_content)
            separated_content.append(("newline", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state
        elif state == whitespace_state:
            match = re.match(whitespace_regex, remaining_content)
            separated_content.append(("white_space", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state
        elif state == word_state:
            match = re.match(word_regex, remaining_content)
            separated_content.append(("word", match.group(0)))
            remaining_content = remaining_content[len(match.group(0)):]
            state = start_state

    return separated_content



if __name__ == '__main__':

    #### Setup ####

    args = sys.argv
    root_path = args[1]
    max_distance = 2



    #### Get File Paths ####

    relevant_folders = [os.path.join("500-Zettelkasten", "Cards")]
    file_paths = []
    for relative_folder in relevant_folders:
        folder = os.path.join(root_path, relative_folder)
        for file_path in os.listdir(folder):
            abs_file_path = os.path.abspath(os.path.join(folder, file_path))
            file_paths.append(abs_file_path)

    file_indices = {file_paths[i]: i for i in range(len(file_paths))}
    num_files = len(file_paths)
    # serialize_dict_to_json(file_paths, "assets/file_paths.json")

    #### Get Files ####

    files = get_file_dict(file_paths)

    #### Separate Files ####

    for file_path in files:
        file = files[file_path]
        file['separated'] = separate_string_fsm(file['body'])

    # serialize_dict_to_json(files, "assets/files.json")

    #### Get Aliases ####

    alias_tree = get_aliases(files)
    # serialize_dict_to_json(alias_tree, "assets/alias_tree.json")

    #### Get Links ####

    links = {}

    for file_path in file_paths:
        file = files[file_path]
        words = [(content, index, type) for index, (type, content) in enumerate(file['separated'])]
        cleaned_words = [word for word in words if word[2] == "word"]
        bad_links = [file_path]
        file_links = get_links(alias_tree, cleaned_words, bad_links)
        links[file_path] = file_links

    # serialize_dict_to_json(links, "assets/links.json")

    #### Get Tags ####

    tags = {}
    for file_path in file_paths:
        file = files[file_path]
        if "tags" in file['frontmatter'] and file['frontmatter']["tags"] != None:
            # print(file['frontmatter'])
            for tag in file['frontmatter']["tags"]:
                if tag not in tags:
                    tags[tag] = []
                tags[tag].append(file_path)
    # serialize_dict_to_json(tags, "assets/tags.json")

    #### Get Graph ####

    file_graph = [[0 for i in range(num_files)] for j in range(num_files)]

    for tag in tags:
        for file1 in tags[tag]:
            for file2 in tags[tag]:
                if file1 != file2:
                    file_graph[file_indices[file1]][file_indices[file2]] = 1
                    file_graph[file_indices[file2]][file_indices[file1]] = 1

    # serialize_dict_to_json(file_graph, "assets/file_graph.json")
    graph = csr_matrix(file_graph)
    dist_matrix, predecessors = dijkstra(csgraph=graph, directed=False, indices=0, return_predecessors=True)

    #### Clean Links by Distance ####

    @functools.cache
    def get_distances(file_index):
        dist_matrix, predecessors = dijkstra(csgraph=graph, directed=False, indices=file_index,
                                             return_predecessors=True)
        return dist_matrix

    clean_links = {}
    for file_path in links:
        if file_path != []:
            for link_inner in links[file_path]:
                linked_file_path = link_inner['link']
                index_1 = file_indices[file_path]
                index_2 = file_indices[linked_file_path]
                distance = get_distances(index_1)[index_2]
                if distance <= max_distance and distance > 0:
                    if file_path not in clean_links:
                        clean_links[file_path] = []
                    clean_links[file_path].append(link_inner)

    # serialize_dict_to_json(clean_links, "assets/clean_links.json")

    #### Add Links ####
    for file_path in files:
        seperated = files[file_path]['separated']
        if file_path in clean_links:
            for link in clean_links[file_path]:
                link_text = "[[" + os.path.basename(link['link']) + "|" + ''.join([string[1] for string in seperated[link['start_index']:(link['end_index']+1)]]) + "]]"
                start_index = link['start_index']
                end_index = link['end_index']
                if end_index > start_index:
                    iter_index = start_index + 1
                    while iter_index < end_index:
                        files[file_path]['separated'].pop(iter_index)
                        iter_index += 1
                files[file_path]['separated'][link['start_index']] = ("link", link_text)

    linked_files = files
    # serialize_dict_to_json(linked_files, "assets/linked_files.json")

    for file_path in file_paths:
        new_body = linked_files[file_path]["frontmatter_string"] + linked_files[file_path]["middle_spaces"] + "".join(
            [string[1] for string in linked_files[file_path]["separated"]])
        with open(file_path, 'w', encoding="utf-8") as file:
            file.write(new_body)