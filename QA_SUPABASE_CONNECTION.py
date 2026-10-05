"""Safe end-to-end Supabase write test for Fahim.

Creates one temporary classroom row, verifies it, and deletes it immediately.
The secret is read only from .streamlit/secrets.toml and is never printed.
"""

from pathlib import Path
from uuid import uuid4

import tomllib
from supabase import create_client


def main():
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        raise FileNotFoundError(
            "لم يتم العثور على .streamlit/secrets.toml داخل مجلد المشروع."
        )

    with secrets_path.open("rb") as file:
        secrets = tomllib.load(file)

    url = secrets.get("SUPABASE_URL")
    key = secrets.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL أو SUPABASE_KEY غير موجود في secrets.toml")

    client = create_client(url, key)
    test_code = f"QA_{uuid4().hex[:10].upper()}"
    inserted_id = None

    try:
        result = (
            client.table("classrooms")
            .insert({"name": "Fahim QA Temporary", "access_code": test_code})
            .execute()
        )
        if not result.data:
            raise RuntimeError("لم تُرجع عملية الإدخال سجلًا.")
        inserted_id = result.data[0]["id"]

        check = (
            client.table("classrooms")
            .select("id,access_code")
            .eq("id", inserted_id)
            .single()
            .execute()
        )
        if not check.data or check.data["access_code"] != test_code:
            raise RuntimeError("تم الإدخال لكن فشل التحقق من السجل.")

        print("OK: Supabase connection, write, and read all succeeded.")
    finally:
        if inserted_id:
            client.table("classrooms").delete().eq("id", inserted_id).execute()
            print("OK: Temporary QA row was deleted.")


if __name__ == "__main__":
    main()
