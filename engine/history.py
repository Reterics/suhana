import tiktoken

def trim_message_history(messages, model='gpt-3.5-turbo', max_tokens=3500):
    encoder = tiktoken.encoding_for_model(model)
    trimmed = [messages[0]]
    token_count = len(encoder.encode(messages[0]["content"]))

    for msg in reversed(messages[1:]):
        msg_tokens = len(encoder.encode(msg["content"]))
        if token_count + msg_tokens > max_tokens:
            break
        trimmed.insert(1, msg)
        token_count += msg_tokens
    return trimmed
