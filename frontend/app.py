from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components

from api_client import (
    build_google_authorization_url,
    create_paste,
    delete_paste,
    exchange_google_code,
    get_health,
    get_paste,
    FRONTEND_URL,
    list_public_pastes,
    login,
    my_pastes,
    signup,
    sync_firebase_user,
    sync_google_user,
    update_paste,
)

st.set_page_config(page_title="MyPaste", page_icon="📝", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

if "google_oauth_state" not in st.session_state:
    st.session_state.google_oauth_state = ""

if "editing_paste_id" not in st.session_state:
    st.session_state.editing_paste_id = None

if "post_create_paste_id" not in st.session_state:
    st.session_state.post_create_paste_id = None


def _query_value(name: str):
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _clear_query_params():
    try:
        st.query_params.clear()
    except Exception:
        pass


def _go_home():
    _clear_query_params()
    st.rerun()


def _go_my_pastes():
    _clear_query_params()
    st.query_params["page"] = "my-pastes"
    st.rerun()


def _go_login():
    _clear_query_params()
    st.query_params["page"] = "login"
    st.rerun()


def _go_new_paste():
    _clear_query_params()
    st.query_params["page"] = "new"
    st.rerun()


def _go_health():
    _clear_query_params()
    st.query_params["page"] = "health"
    st.rerun()


def _go_paste(paste_id: str):
    _clear_query_params()
    st.query_params["p"] = paste_id
    st.rerun()


def _logout():
    st.session_state.user = None
    st.session_state.editing_paste_id = None
    st.session_state.post_create_paste_id = None
    _clear_query_params()
    st.rerun()


def _backend_login_user(user_payload: dict):
    def _pick_user_id(synced: dict) -> str:
        user_id = synced.get("user_id") or synced.get("userId")
        if not user_id:
            raise RuntimeError("Sync response is missing user id")
        return str(user_id)

    if user_payload.get("provider") == "firebase":
        synced = sync_firebase_user(user_payload["idToken"])
        user_payload["userId"] = _pick_user_id(synced)
        return user_payload

    synced = sync_google_user(user_payload["email"], user_payload["google_id"])
    user_payload["userId"] = _pick_user_id(synced)
    return user_payload


def _handle_google_callback():
    code = _query_value("code")
    state = _query_value("state")
    error = _query_value("error")

    if not code:
        if error:
            st.error(f"Google login failed: {error}")
            _clear_query_params()
        return

    expected_state = st.session_state.google_oauth_state
    # In local Streamlit runs, session state can be regenerated across OAuth redirects.
    if expected_state and state and state != expected_state:
        st.warning("Google login state changed across redirect. Continuing with local mode.")

    try:
        profile = exchange_google_code(code)
        user = _backend_login_user(
            {
                "provider": "google",
                "email": profile["email"],
                "google_id": profile["google_id"],
            }
        )
        st.session_state.user = user
        st.session_state.google_oauth_state = ""
        _clear_query_params()
        st.success("Đăng nhập Google thành công")
        st.rerun()
    except Exception as exc:
        st.error(f"Không thể đăng nhập Google: {exc}")
        _clear_query_params()


def _set_google_login_state():
    st.session_state.google_oauth_state = secrets.token_urlsafe(32)


def _current_page():
    paste_id = _query_value("p")
    if paste_id:
        return "paste"

    page = _query_value("page") or "home"
    return page


def _render_navigation_panel(page: str):
    st.sidebar.title("MyPaste")

    if st.session_state.user:
        if st.sidebar.button("Home", use_container_width=True):
            _go_home()
        if st.sidebar.button("My Pastes", use_container_width=True):
            _go_my_pastes()
        if st.sidebar.button("Health", use_container_width=True):
            _go_health()
        if st.sidebar.button("New Paste", use_container_width=True, type="primary"):
            _go_new_paste()
    else:
        if st.sidebar.button("Home", use_container_width=True):
            _go_home()
        if st.sidebar.button("Health", use_container_width=True):
            _go_health()
        if st.sidebar.button("Login", use_container_width=True, type="primary"):
            _go_login()

    st.sidebar.markdown("---")
    if st.session_state.user:
        st.sidebar.caption(f"Signed in as\n{st.session_state.user.get('email', '')}")
        if st.sidebar.button("Logout", use_container_width=True):
            _logout()
    else:
        st.sidebar.caption("Not signed in")


def _format_dt(value):
    if not value:
        return "Never"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _preview_content(content: str, max_chars: int = 420, max_lines: int = 8) -> str:
    raw = (content or "").replace("\r\n", "\n")
    if len(raw) > max_chars:
        raw = raw[:max_chars] + "..."
    lines = raw.split("\n")
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["..."]
    return "\n".join(lines)


def _render_content_preview(content: str, language: str):
    st.code(_preview_content(content), language=language or "text")


def _render_copy_link_button(share_link: str):
    components.html(
        f"""
        <button id="copy-btn" style="
            width: 100%;
            padding: 8px 10px;
            border-radius: 8px;
            border: 1px solid #4b9bff;
            background: #2563eb;
            color: white;
            cursor: pointer;">
            Copy Link
        </button>
        <div id="copy-status" style="margin-top:6px; color:#16a34a; font-size:12px;"></div>
        <script>
            const copyBtn = document.getElementById("copy-btn");
            const copyStatus = document.getElementById("copy-status");
            copyBtn.addEventListener("click", async () => {{
                try {{
                    await navigator.clipboard.writeText({json.dumps(share_link)});
                    copyStatus.innerText = "Successful";
                }} catch (e) {{
                    copyStatus.innerText = "Cannot copy automatically. Copy manually from link.";
                }}
            }});
        </script>
        """,
        height=70,
    )


def _render_google_login_link(auth_url: str):
    st.markdown(
        f"""
        <a href="{auth_url}" target="_self" style="
            display:inline-block;
            width:100%;
            text-align:center;
            padding:10px 12px;
            border-radius:8px;
            background:#2563eb;
            color:#ffffff;
            text-decoration:none;
            font-weight:600;">
            Continue with Google
        </a>
        """,
        unsafe_allow_html=True,
    )


def _render_login_page():
    st.title("Sign in to MyPaste")
    tab_signin, tab_signup = st.tabs(["Sign in", "Create account"])

    with tab_signin:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign in")

        if submitted:
            try:
                firebase_user = login(email, password)
                user = _backend_login_user(
                    {
                        "provider": "firebase",
                        "email": firebase_user.get("email", email),
                        "idToken": firebase_user["idToken"],
                        "uid": firebase_user.get("localId", ""),
                    }
                )
                st.session_state.user = user
                st.success("Signed in successfully")
                _clear_query_params()
                st.rerun()
            except Exception as exc:
                st.error(f"Sign in failed: {exc}")

        st.markdown("### Google login")
        if not st.session_state.google_oauth_state:
            _set_google_login_state()
        try:
            auth_url = build_google_authorization_url(st.session_state.google_oauth_state)
            _render_google_login_link(auth_url)
        except Exception as exc:
            st.warning(f"Google login is not configured yet: {exc}")

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            submitted = st.form_submit_button("Create account")

        if submitted:
            try:
                signup(email, password)
                st.success("Account created. You can sign in now.")
            except Exception as exc:
                st.error(f"Signup failed: {exc}")


def _render_paste_form(user: dict):
    st.subheader("Create a paste")
    with st.form("create_paste_form"):
        title = st.text_input("Title")
        language = st.selectbox(
            "Language",
            ["text", "python", "javascript", "typescript", "json", "markdown", "bash", "sql"],
        )
        visibility = st.selectbox("Visibility", ["public", "private"])
        custom_id = st.text_input("Custom ID (optional)")
        content = st.text_area("Content (max 2048 chars)", height=260, max_chars=2048)
        submitted = st.form_submit_button("Create paste")

    if submitted:
        if len(content or "") > 2048:
            st.error("Content must be 2048 characters or less.")
            return

        try:
            paste = create_paste(
                user,
                {
                    "title": title,
                    "content": content,
                    "language": language,
                    "visibility": visibility,
                    "customId": custom_id or None,
                },
            )
            st.session_state.post_create_paste_id = paste["id"]
            _go_paste(paste["id"])
        except Exception as exc:
            st.error(f"Could not create paste: {exc}")


def _render_edit_form(user: dict, paste: dict):
    st.subheader("Edit paste")
    with st.form("edit_paste_form"):
        title = st.text_input("Title", value=paste.get("title", ""))
        language = st.text_input("Language", value=paste.get("language", "text"))
        visibility = st.selectbox("Visibility", ["public", "private"], index=0 if paste.get("visibility") == "public" else 1)
        content = st.text_area("Content (max 2048 chars)", value=paste.get("content", ""), height=260, max_chars=2048)
        submitted = st.form_submit_button("Save changes")

    if submitted:
        if len(content or "") > 2048:
            st.error("Content must be 2048 characters or less.")
            return

        try:
            update_paste(
                paste["id"],
                user,
                {
                    "title": title,
                    "content": content,
                    "language": language,
                    "visibility": visibility,
                },
            )
            st.session_state.editing_paste_id = None
            st.success("Paste updated")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not update paste: {exc}")


def _render_paste_page():
    paste_id = _query_value("p")
    if not paste_id:
        st.error("Missing paste id")
        return

    try:
        paste = get_paste(paste_id, st.session_state.user)
    except Exception as exc:
        st.error(f"Could not load paste: {exc}")
        return

    st.title(paste.get("title") or paste_id)
    
    header_cols = st.columns([2, 1])
    with header_cols[0]:
        st.caption(f"Paste ID: {paste_id}")
    with header_cols[1]:
        share_link = f"{FRONTEND_URL}?p={paste_id}"
        _render_copy_link_button(share_link)
    
    if st.session_state.post_create_paste_id == paste_id:
        st.success("Paste created successfully")
        st.session_state.post_create_paste_id = None

    st.write(f"**Language:** {paste.get('language', 'text')}")
    st.write(f"**Visibility:** {paste.get('visibility', 'public')}")
    st.write(f"**Posted by:** {paste.get('userId', 'Anonymous')}")
    st.write(f"**Created:** {_format_dt(paste.get('createdAt'))}")

    if st.session_state.user and paste.get("canEdit"):
        owner_col, action_col = st.columns(2)
        with owner_col:
            if st.button("Edit", use_container_width=True):
                st.session_state.editing_paste_id = paste_id
        with action_col:
            if st.button("Delete", type="secondary", use_container_width=True):
                try:
                    delete_paste(paste_id, st.session_state.user)
                    st.session_state.editing_paste_id = None
                    st.success("Paste deleted")
                    _clear_query_params()
                    st.query_params["page"] = "my-pastes"
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not delete paste: {exc}")

    is_editing = st.session_state.editing_paste_id == paste_id and paste.get("canEdit")
    if is_editing:
        st.divider()
        _render_edit_form(st.session_state.user, paste)

    if not is_editing:
        st.divider()
        st.code(paste.get("content", ""), language=paste.get("language", "text"))


def _render_home_page():
    st.title("Home")

    search = st.text_input("Search public paste by ID", placeholder="e.g. abc123")

    try:
        search_text = search.strip() or None
        pastes = list_public_pastes(skip=0, limit=10, search=search_text)

        st.subheader("Search results" if search_text else "Recent public pastes")
        if not pastes:
            st.info("No public pastes found.")
        else:
            for paste in pastes:
                with st.container(border=True):
                    top_left, top_right = st.columns([3, 1])
                    with top_left:
                        st.subheader(paste.get("title") or paste["id"])
                        st.caption(
                            f"{paste.get('language', 'text')} | By {paste.get('userId', 'Anonymous')} | Created {_format_dt(paste.get('createdAt'))}"
                        )
                    with top_right:
                        if st.button("Open", key=f"open_public_{paste['id']}", use_container_width=True):
                            _go_paste(paste["id"])

                    _render_content_preview(
                        paste.get("content", "") or "",
                        paste.get("language", "text"),
                    )
    except Exception as exc:
        st.error(f"Could not load public pastes: {exc}")


def _render_my_pastes_page():
    st.title("My pastes")
    if not st.session_state.user:
        st.info("Please sign in first.")
        return

    try:
        pastes = my_pastes(st.session_state.user)
    except Exception as exc:
        st.error(f"Could not load your pastes: {exc}")
        return

    if not pastes:
        st.info("You have not created any pastes yet.")
        return

    for paste in pastes:
        with st.container(border=True):
            top_left, top_right = st.columns([3, 1])
            with top_left:
                st.subheader(paste.get("title") or paste["id"])
                st.caption(
                    f"{paste.get('visibility', 'public')} | {paste.get('language', 'text')} | Created {_format_dt(paste.get('createdAt'))}"
                )
                if paste.get("isExpired"):
                    st.warning("Expired")
            with top_right:
                st.button("Open", key=f"open_{paste['id']}", on_click=_go_paste, args=(paste["id"],), use_container_width=True)

            _render_content_preview(
                paste.get("content", "") or "",
                paste.get("language", "text"),
            )


def _render_health_page():
    st.title("System Health")
    try:
        data = get_health()
    except Exception as exc:
        st.error(f"Could not load health data: {exc}")
        return

    status = data.get("status", "unknown")
    if status == "ok":
        st.success(f"Status: {status}")
    else:
        st.warning(f"Status: {status}")
        if data.get("error"):
            st.caption(f"Error: {data['error']}")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Users", int(data.get("totalUsers", 0)))
        st.metric("Total Pastes", int(data.get("totalPastes", 0)))
    with col2:
        st.metric("Public Pastes", int(data.get("publicPastes", 0)))
        st.metric("Uptime (seconds)", int(data.get("uptimeSeconds", 0)))


_handle_google_callback()

st.title("MyPaste")
st.caption("Create and share text snippets easily.")

page = _current_page()
_render_navigation_panel(page)
st.divider()

if page == "login" and not st.session_state.user:
    _render_login_page()
elif page == "my-pastes":
    if st.session_state.user:
        _render_my_pastes_page()
    else:
        st.info("Please sign in to view your pastes.")
        _render_login_page()
elif page == "paste":
    _render_paste_page()
elif page == "new":
    if st.session_state.user:
        _render_paste_form(st.session_state.user)
    else:
        st.info("Please sign in to create a paste.")
        _render_login_page()
elif page == "health":
    _render_health_page()
else:
    _render_home_page()
