import streamlit as st
import json
import os
from datetime import datetime
import urllib.request
import urllib.parse
from typing import List, Dict, Generator

# Ollama API URL
API_URL = "http://127.0.0.1:11434"
CHAT_HISTORY_FILE = "chat_history.json"

# Function to fetch available models
def fetch_models() -> List[str]:
    try:
        with urllib.request.urlopen(urllib.parse.urljoin(API_URL, "/api/tags")) as response:
            data = json.load(response)
            return [model["name"] for model in data["models"]]
    except Exception as e:
        st.sidebar.error(f"Error fetching models: {e}")
        return []

# Function to generate AI response (streaming)
def generate_ai_response(model: str, messages: List[Dict]) -> Generator:
    url = urllib.parse.urljoin(API_URL, "/api/chat")
    request = urllib.request.Request(
        url,
        data=json.dumps({"model": model, "messages": messages, "stream": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as resp:
            for line in resp:
                data = json.loads(line.decode("utf-8"))
                if "message" in data:
                    yield data["message"]["content"]
    except Exception as e:
        st.error(f"Error: {e}")

# Function to load chat history from file as a flat list, then group by date
def load_chat_history() -> Dict[str, List[Dict]]:
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r") as f:
                chats = json.load(f)  # Expecting a JSON array
        except Exception as e:
            st.error(f"Error loading chat history: {e}")
            chats = []
    else:
        chats = []
    daily_chats = {}
    for chat in chats:
        date = chat["timestamp"].split(" ")[0]
        daily_chats.setdefault(date, []).append(chat)
    return daily_chats

# Helper to flatten the grouped chat history back into a list
def flatten_chat_history(chat_dict: Dict[str, List[Dict]]) -> List[Dict]:
    all_chats = []
    for messages in chat_dict.values():
        all_chats.extend(messages)
    all_chats.sort(key=lambda x: x["timestamp"])
    return all_chats

# Function to save the entire chat history (flattened) to file
def save_all_chat_history(chats: List[Dict]):
    try:
        with open(CHAT_HISTORY_FILE, "w") as f:
            json.dump(chats, f, indent=4)
    except Exception as e:
        st.error(f"Error saving chat history: {e}")

# Function to append a single chat entry to the file
def append_chat_entry(entry: Dict):
    chats = []
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r") as f:
                chats = json.load(f)
        except Exception as e:
            st.error(f"Error reading chat history: {e}")
            chats = []
    chats.append(entry)
    save_all_chat_history(chats)

# Streamlit App
def main():
    st.title("AI ChatBOT Interface")

    # Sidebar for settings
    st.sidebar.header("Settings")

    # Fetch models dynamically
    if "models" not in st.session_state:
        st.session_state.models = fetch_models()

    # Refresh button to fetch models
    if st.sidebar.button("Refresh Models"):
        st.session_state.models = fetch_models()

    # Model selection dropdown
    if st.session_state.models:
        model = st.sidebar.selectbox("Select Model", st.session_state.models)
    else:
        st.sidebar.error("No models available. Please check the Ollama server.")

    # Load chat history into session state if not already loaded
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = load_chat_history()

    # Sidebar Chat History: Each date has an expander with nested containers for each exchange
    st.sidebar.header("Chat History")
    for date, chats in st.session_state.chat_history.items():
        with st.sidebar.expander(date, expanded=False):
            i = 0
            while i < len(chats):
                with st.container():
                    # Display user's message if available
                    if chats[i]["user"] == "You":
                        st.write(f"**You:** {chats[i]['message']}")
                        user_msg_index = i
                        i += 1
                        # If the next message is from Ollama, show it as the reply
                        if i < len(chats) and chats[i]["user"] == "Ollama":
                            st.write(f"**Ollama:** {chats[i]['message']}")
                            ollama_msg_index = i
                            i += 1
                        else:
                            ollama_msg_index = None
                    else:
                        # In case it starts with an Ollama message
                        st.write(f"**{chats[i]['user']}:** {chats[i]['message']}")
                        user_msg_index = i
                        ollama_msg_index = None
                        i += 1

                    # Delete button for this exchange
                    if st.button("Delete Exchange", key=f"delete_exchange_{date}_{user_msg_index}"):
                        # Determine indices to delete from the exchange
                        indices_to_delete = [user_msg_index]
                        if ollama_msg_index is not None:
                            indices_to_delete.append(ollama_msg_index)
                        # Filter out the messages to be deleted
                        new_chats = [chat for idx, chat in enumerate(chats) if idx not in indices_to_delete]
                        st.session_state.chat_history[date] = new_chats
                        save_all_chat_history(flatten_chat_history(st.session_state.chat_history))
                        st.rerun()

    # Main chat interface: Display current day's chat (remains open)
    st.header("Chat")
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in st.session_state.chat_history:
        st.session_state.chat_history[today] = []
    for idx, chat in enumerate(st.session_state.chat_history[today]):
        with st.container():
            st.write(f"**{chat['timestamp']} - {chat['user']}:** {chat['message']}")
            if st.button("Delete", key=f"delete_main_{today}_{idx}"):
                st.session_state.chat_history[today].pop(idx)
                save_all_chat_history(flatten_chat_history(st.session_state.chat_history))
                st.rerun()

    # Fixed input box at the bottom using a form (clear_on_submit ensures the box clears after sending)
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("You:")
        submitted = st.form_submit_button("Send")
        if submitted and user_input:
            # Append user's message
            chat_entry_user = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user": "You",
                "message": user_input
            }
            st.session_state.chat_history.setdefault(today, []).append(chat_entry_user)
            append_chat_entry(chat_entry_user)
            
            messages = [{"role": "user", "content": user_input}]
            
            st.write("Ollama: ")
            response_container = st.empty()
            full_response = ""
            for chunk in generate_ai_response(model, messages):
                full_response += chunk
                response_container.markdown(full_response)
            
            # Append Ollama's response
            chat_entry_ollama = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user": "Ollama",
                "message": full_response
            }
            st.session_state.chat_history.setdefault(today, []).append(chat_entry_ollama)
            append_chat_entry(chat_entry_ollama)
            st.rerun()

if __name__ == "__main__":
    main()
