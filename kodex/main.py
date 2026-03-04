import json
import os
import sys

from openai import OpenAI

from kodex.tools import load_schemas, execute

_PKG = os.path.dirname(__file__)
_USER = os.path.expanduser("~/.kodex")


def _resolve(name):
    """Return ~/.kodex/<name> if it exists, else the package default."""
    user = os.path.join(_USER, name)
    return user if os.path.exists(user) else os.path.join(_PKG, name)


def _load_config():
    with open(os.path.join(_PKG, "models.json")) as f:
        config = json.load(f)
    user_conf = os.path.join(_USER, "models.json")
    if os.path.exists(user_conf):
        with open(user_conf) as f:
            config.update(json.load(f))
    return config


def _load_keys():
    keys_path = os.path.join(_USER, "keys.json")
    if os.path.exists(keys_path):
        with open(keys_path) as f:
            return json.load(f)
    fallback = os.environ.get("OPENAI_API_KEY")
    if fallback:
        return {"_default": fallback}
    print("Create ~/.kodex/keys.json or set OPENAI_API_KEY.")
    sys.exit(1)


def _get_api_key(keys, endpoint):
    return keys.get(endpoint) or keys.get("_default") or next(iter(keys.values()))


def main():
    config = _load_config()
    endpoints = config["endpoints"]
    endpoint = config["endpoint"]
    model = config["model"]

    keys = _load_keys()
    api_key = _get_api_key(keys, endpoint)
    client = OpenAI(base_url=endpoints[endpoint]["base_url"], api_key=api_key)

    with open(_resolve("prompt.txt")) as f:
        prompt = f.read().format(cwd=os.getcwd())
    schemas = load_schemas(_resolve("tools.json"))
    messages = [{"role": "system", "content": prompt}]

    models = endpoints[endpoint]["models"]
    print(f"kodex | {models[model]} | {endpoint}")
    print(f"cwd: {os.getcwd()}")
    print("Type /help for commands.\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        if user_input == "/exit":
            break
        elif user_input == "/model":
            models = endpoints[endpoint]["models"]
            print(f"  endpoint: {endpoint}")
            for k, v in models.items():
                marker = " *" if k == model else ""
                print(f"  {k}: {v}{marker}")
            choice = input("Choose: ").strip().lower()
            if choice in models:
                model = choice
                print(f"Model: {models[model]}")
            continue
        elif user_input == "/endpoint":
            for name, ep in endpoints.items():
                marker = " *" if name == endpoint else ""
                print(f"  {name}{marker}")
                for k, v in ep["models"].items():
                    print(f"    {k}: {v}")
            choice = input("Choose: ").strip().lower()
            if choice in endpoints:
                endpoint = choice
                api_key = _get_api_key(keys, endpoint)
                client = OpenAI(base_url=endpoints[endpoint]["base_url"], api_key=api_key)
                models = endpoints[endpoint]["models"]
                model = next(iter(models))
                print(f"Endpoint: {endpoint}, model: {models[model]}")
            continue
        elif user_input == "/help":
            print("/model    - Switch model")
            print("/endpoint - Switch endpoint")
            print("/exit     - Exit")
            continue

        messages.append({"role": "user", "content": user_input})

        # agentic loop: keep going while the model wants to call tools
        while True:
            models = endpoints[endpoint]["models"]
            response = client.chat.completions.create(
                model=models[model], messages=messages, tools=schemas
            )
            msg = response.choices[0].message
            messages.append(msg)

            if msg.content:
                print(msg.content)

            if not msg.tool_calls:
                break

            for tc in msg.tool_calls:
                print(f"\n--- {tc.function.name} ---")
                result = execute(tc.function.name, tc.function.arguments)
                print(result)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
