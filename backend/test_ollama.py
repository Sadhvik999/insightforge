
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"


def ask_ollama(question):

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ],
        "stream": False
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        return response.json()["message"]["content"]

    except requests.exceptions.RequestException as e:
        return f"Connection Error: {e}"


if __name__ == "__main__":

    question = "What is data analysis? Explain in simple words."

    answer = ask_ollama(question)

    print("\nQwen Response:\n")
    print(answer)
