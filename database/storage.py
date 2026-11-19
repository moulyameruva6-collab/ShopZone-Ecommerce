
import os
import uuid

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

BUCKET_NAME = "product-images"


def upload_product_image(file):

    if not file or not file.filename:
        return None, None

    extension = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"

    try:
        file_data = file.read()

        print("Uploading image:", filename)

        supabase.storage.from_(BUCKET_NAME).upload(
            path=filename,
            file=file_data,
            file_options={
                "content-type": file.content_type or "image/jpeg",
                "upsert": "false"
            }
        )

        image_url = supabase.storage.from_(
            BUCKET_NAME
        ).get_public_url(filename)

        print("IMAGE UPLOADED:", image_url)

        return filename, image_url

    except Exception as e:
        print("SUPABASE IMAGE UPLOAD ERROR:", repr(e))
        return None, None
