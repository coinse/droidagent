import copy

"""
Getters
"""

def __safe_dict_get(d, key, default=None):
    return d[key] if (key in d) else default


def __get_all_children(view_dict, views):
        """
        Get temp view ids of the given view's children
        :param view_dict: dict, an element of DeviceState.views
        :return: set of int, each int is a child node id
        """
        children = __safe_dict_get(view_dict, 'children')
        if not children:
            return set()
        children = set(children)
        for child in children:
            children_of_child = __get_all_children(views[child], views)
            children.union(children_of_child)
        return children


"""
Process DroidBot view tree
"""
def minimize_view_tree(view_tree):
    """
    Remove non-informative nodes from the view tree
    """
    view_tree = copy.deepcopy(view_tree)
    
    new_root_elems = []
    for root_elem in prune_elements(view_tree):
        new_root_elems.extend(additionally_prune_elements(root_elem))

    return new_root_elems


def prune_elements(elem):
    if is_meaningful_element(elem):
        # If the current node is interactable or has a text property, recursively prune its children
        if "children" in elem and isinstance(elem["children"], list):
            new_children = []
            for child in elem["children"]:
                new_children.extend(prune_elements(child))
            elem["children"] = new_children
        return [elem]
    else:
        # If the current node is either not interactable or doesn't have a text property, recursively prune its children and lift them
        if "children" in elem:
            lifted_children = []
            for child in elem["children"]:
                lifted_children.extend(prune_elements(child))
            return lifted_children
        return []


def is_meaningful_element(elem):
    if not elem.get('visible', False):
        return False

    if not elem.get('enabled', False):
        return False
    
    if elem.get('package') == 'com.android.documentsui': # hotfix for DocumentsUI (removed screenshot files are cached)
        file_picker_elem_text = elem.get('text')
        if file_picker_elem_text is not None:
            file_picker_elem_text = file_picker_elem_text.strip()
            if file_picker_elem_text.startswith('screen_') and file_picker_elem_text.endswith('.png'):
                elem['children'] = []
                del elem['text']
                return False

        file_picker_elem_content_desc = elem.get('content_description')
        if file_picker_elem_content_desc is not None and 'Photo taken on' in file_picker_elem_content_desc:
            elem['children'] = []
            del elem['content_description']
            return False

        if elem.get('resource_id') == 'android:id/title':
            elem['clickable'] = True
            return True

    if any(elem.get(property_name, False) for property_name in ['clickable', 'long_clickable', 'editable', 'scrollable', 'checkable']):
        return True 
    if elem.get('text') is not None and len(elem['text'].strip()) > 0:
        return True

    return False


def additionally_prune_elements(elem):
    # if the current node has only one child that doesn't have any children, lift the child
    if len(elem.get('children', [])) == 1 and len(elem['children'][0].get('children', [])) == 0:
        only_child = elem['children'][0]
        if any(only_child.get(property_name, False) for property_name in ['clickable', 'long_clickable', 'editable', 'scrollable', 'checkable']):
            return [elem]

        if only_child.get('text') is not None and len(only_child['text'].strip()) > 0 and elem.get('text') is None:
            elem['text'] = only_child['text']
            elem['children'] = []

    return [elem]



