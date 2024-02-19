from functools import cached_property

import json
import copy


class Widget:
    def __init__(self):
        self.view_id = None
        self.widget_type = None
        self.possible_action_types = []

    def from_dict(self, elem_dict):
        self.view_id = elem_dict.get('ID', None)
        self.widget_type = elem_dict['widget_type']
        self.possible_action_types = elem_dict.get('possible_action_types', [])
        self.children = elem_dict.get('children', [])

        if 'children' in elem_dict:
            del elem_dict['children']
        
        self.elem_dict = elem_dict

        return self

    def to_dict(self, include_id=True, only_rep_property=True):
        children = [child.to_dict(include_id=include_id) for child in self.children]
        elem_dict = copy.deepcopy(self.elem_dict)

        del elem_dict['class']
        del elem_dict['bounds']
        if not include_id and 'ID' in elem_dict:
            del elem_dict['ID']

        if only_rep_property:
            if 'text' in elem_dict:
                if 'resource_id' in elem_dict:
                    del elem_dict['resource_id']
                if 'content_description' in elem_dict:
                    del elem_dict['content_description']
            
        if 'view_str' in elem_dict:
            del elem_dict['view_str']

        if len(children) > 0:
            elem_dict['children'] = children

        return elem_dict

    @cached_property
    def bounds(self):
        return self.elem_dict['bounds']
        
    @cached_property
    def text(self):
        return self.elem_dict.get('text', None)

    @cached_property
    def resource_id(self):
        return self.elem_dict.get('resource_id', None)

    @cached_property
    def content_description(self):
        return self.elem_dict.get('content_description', None)

    @cached_property
    def all_text(self):
        texts = []
        if self.text is not None and len(self.text.strip()) > 0:
            if len(self.text) > 50:
                texts.append(self.text[:50] + '[...]')
            else:
                texts.append(self.text)

        for child in self.children:
            texts.extend(child.all_text)
        
        return texts

    @cached_property
    def state(self):
        return self.elem_dict.get('state', [])

    @cached_property
    def signature(self):
        immutable_props = ['content_description', 'resource_id']
        if 'set_text' not in self.possible_action_types:
            immutable_props.append('text')

        ingredients = []
        for prop in immutable_props:
            if prop in self.elem_dict and self.elem_dict[prop] is not None and len(self.elem_dict[prop].strip()) > 0:
                ingredients.append(self.elem_dict[prop])
        
        # also use concatenated children's signature
        ingredients.extend([child.signature for child in self.children])

        if len(ingredients) == 0:
            # non-describable widget...
            ingredients = [str(self.elem_dict['bounds'])]

        ingredients.insert(0, self.widget_type)

        return '-'.join(ingredients)

    def __repr__(self):
        return self.dump()

    def __str__(self):
        return self.stringify()

    def dump(self, indent=2):
        """
        Stringify the widget including its children
        {
            "ID": 10,
            "widget_type": "Spinner",
            "resource_id": "com.ichi2.anki:id/toolbar_spinner",
            "possible_action_types": [
                "touch",
                "long_touch",
                "scroll"
            ],
            "children": [
                {
                "widget_type": "TextView",
                "text": "My Filtered Deck",
                "resource_id": "com.ichi2.anki:id/dropdown_deck_name"
                },
                {
                "widget_type": "TextView",
                "text": "6 cards shown",
                "resource_id": "com.ichi2.anki:id/dropdown_deck_counts"
                }
            ]
        }
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def stringify(self, include_children_text=True):
        """
        natural language description of the widget
        """
        widget_type = self.widget_type
        widget_desc = ''

        if len(self.state) > 0:
            state = ', '.join(self.state)
            widget_desc = f'{state} '

        if self.elem_dict.get('is_password', False):
            widget_desc += 'password textfield'
        
        elif 'EditText' in widget_type:
            widget_desc += 'textfield'
        elif 'Button' in widget_type:
            widget_desc += 'button'
        elif 'CheckBox' in widget_type:
            widget_desc += 'checkbox'
        elif 'RadioButton' in widget_type:
            widget_desc += 'radio button'
        elif 'Spinner' in widget_type:
            widget_desc += 'dropdown field'
        elif widget_type.endswith('Tab'):
            widget_desc += 'tab'
        
        else:
            if 'touch' in self.possible_action_types:
                widget_desc += 'button'
            elif 'scroll' in self.possible_action_types:
                widget_desc += 'scrollable area'
            elif 'set_text' in self.possible_action_types:
                widget_desc += 'textfield'
            elif 'TextView' in widget_type:
                widget_desc += 'textview'
            elif 'ImageView' in widget_type:
                widget_desc += 'imageview'
            elif 'LinearLayout' in widget_type:
                widget_desc += 'linearlayout'
            elif 'RelativeLayout' in widget_type:
                widget_desc += 'relativelayout'
            elif 'FrameLayout' in widget_type:
                widget_desc += 'framelayout'
            elif 'GridLayout' in widget_type:
                widget_desc += 'gridlayout'
            elif 'RecyclerView' in widget_type:
                widget_desc += 'recyclerview'
            elif 'ListView' in widget_type:
                widget_desc += 'listview'
            else:
                widget_desc += 'widget'
        
        widget_desc = 'an ' + widget_desc if widget_desc[0] in ['a', 'e', 'i', 'o', 'u'] else 'a ' + widget_desc

        if include_children_text:
            if len(self.all_text) > 3:
                text = ', '.join(self.all_text[:3]) + f'[...and more]'
            else:
                text = ", ".join(self.all_text) if len(self.all_text) > 0 else None
        else:
            text = self.text
        content_description = self.elem_dict.get('content_description', None)
        resource_id = self.elem_dict.get('resource_id', None)

        text_desc = []
        if text is not None:
            text_desc.append(f'text "{text}"')
        elif content_description is not None:
            text_desc.append(f'content_desc "{content_description}"')
        elif resource_id is not None:
            text_desc.append(f'resource_id "{resource_id}"')

        if len(text_desc) > 0:
            text_desc = ' and '.join(text_desc)
            return f'{widget_desc} that has {text_desc}'
        
        return widget_desc
