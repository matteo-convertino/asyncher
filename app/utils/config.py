from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # server config | required
    pull_url: str
    push_url: str

    # uniquely identifies a data (and sub data) | optional
    unique_key: str = "unique"

    # primary key to ignore during the loop | optional
    primary_key: str = "id"

    # client sync attributes | optional
    is_new_key: str = "is_new"
    deleted_key: str = "deleted"
    updated_key: str = "updated"

    # key that has to be managed for sorting (ex: position) | optional
    sorting_key: str | None = None

    # server auditing params | optional
    created_at_key: str | None = None
    updated_at_key: str | None = None
    deleted_at_key: str | None = None
