import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="Chat with your documents", page_icon="📄")


def logout():
    for key in ("token", "email", "messages"):
        st.session_state.pop(key, None)


def api(method, path, timeout=120, **kwargs):
    headers = {}
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        r = requests.request(method, f"{API_URL}{path}", headers=headers, timeout=timeout, **kwargs)
    except requests.exceptions.RequestException:
        st.error("Cannot reach the API. Is the backend running?")
        return None
    if r.status_code == 401 and st.session_state.get("token"):
        logout()
        st.session_state.notice = "Your session expired. Please log in again."
        st.rerun()
    return r


def error_text(r):
    detail = r.json().get("detail", "Something went wrong.")
    if isinstance(detail, list):
        return "Please enter a valid email and a password of 8 to 64 characters."
    return detail


def do_login(email, password):
    r = api("POST", "/auth/login", data={"username": email, "password": password})
    if r is None:
        return False
    if r.ok:
        st.session_state.token = r.json()["access_token"]
        st.session_state.email = email.strip().lower()
        return True
    st.error(error_text(r))
    return False


def auth_screen():
    st.title("📄 Chat with your documents")
    st.caption("Create an account to upload your own PDFs and ask questions about them.")
    if notice := st.session_state.pop("notice", None):
        st.warning(notice)
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted and do_login(email, password):
            st.rerun()

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="su_email")
            password = st.text_input("Password (8 to 64 characters)", type="password", key="su_pw")
            confirm = st.text_input("Confirm password", type="password", key="su_pw2")
            submitted = st.form_submit_button("Create account")
        if submitted:
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                r = api("POST", "/auth/signup", json={"email": email.strip(), "password": password})
                if r is not None:
                    if r.ok and do_login(email, password):
                        st.rerun()
                    elif not r.ok:
                        st.error(error_text(r))


def main_app():
    with st.sidebar:
        st.write(f"Signed in as **{st.session_state.email}**")
        if st.button("Log out"):
            logout()
            st.rerun()
        st.divider()

        st.header("Upload a PDF")
        uploaded = st.file_uploader("Choose a PDF", type="pdf")
        if uploaded and st.button("Process document"):
            with st.spinner("Reading and indexing... this can take a minute"):
                r = api("POST", "/upload", timeout=600,
                        files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")})
            if r is not None:
                if r.ok:
                    st.success(f"Indexed {r.json()['chunks_added']} chunks from {uploaded.name}")
                else:
                    st.error(error_text(r))

        st.header("Your documents")
        r = api("GET", "/documents")
        docs = r.json() if r is not None and r.ok else []
        if not docs:
            st.caption("No documents yet.")
        for d in docs:
            c1, c2 = st.columns([4, 1])
            c1.write(f"{d['filename']} ({d['chunks']} chunks)")
            if c2.button("🗑", key=f"del_{d['id']}"):
                api("DELETE", f"/documents/{d['id']}")
                st.rerun()

    st.title("📄 Chat with your documents")
    st.caption("Answers come only from your own documents, with page citations.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                st.caption("Sources: " + ", ".join(f"{s['file']} p.{s['page']}" for s in msg["sources"]))

    if question := st.chat_input("Ask a question about your documents"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                r = api("POST", "/ask", json={"question": question})
            if r is not None and r.ok:
                data = r.json()
                answer_text, sources = data["answer"], data["sources"]
            else:
                answer_text, sources = "Sorry, something went wrong while answering.", []
            st.markdown(answer_text)
            if sources:
                st.caption("Sources: " + ", ".join(f"{s['file']} p.{s['page']}" for s in sources))
        st.session_state.messages.append({"role": "assistant", "content": answer_text, "sources": sources})


if st.session_state.get("token"):
    main_app()
else:
    auth_screen()