def add_period(text):
    if text.endswith('.'):
        return text
    else:
        return text + '.'

def remove_quotes(text):
    text = text.replace('"', '').replace("'", '')
    text = text.replace('\\n', '[NEWLINE]')
    text = text.replace('\\', '')
    return text

def remove_period(text):
    if text.endswith('.'):
        return text[:-1]
    else:
        return text