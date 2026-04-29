from __future__ import annotations

import pyrebase
import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore

def get_pyrebase_auth():
    firebase_cfg = st.secrets["firebase_client"]
    firebase_app = pyrebase.initialize_app(firebase_cfg)
    return firebase_app.auth()


def get_firebase_web_api_key() -> str:
    return str(st.secrets["firebase_client"]["apiKey"])


def init_firebase_admin():
    if not firebase_admin._apps:
        cred_dict = dict(st.secrets["firebase_admin"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()


def get_firestore():
    init_firebase_admin()
    return firestore.client()
