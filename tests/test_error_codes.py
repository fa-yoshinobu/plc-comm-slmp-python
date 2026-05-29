from slmp import (
    SlmpError,
    get_end_code_message,
    get_end_code_name,
    is_remote_password_end_code,
)


def test_end_code_names_and_messages() -> None:
    assert get_end_code_name(0x1080) == "slmp_end_code_1080"
    assert get_end_code_message(0x1080) == "The number of writes to the flash ROM has exceeded 100000."
    assert get_end_code_message(0x1080, "ja") == "フラッシュROMへの書込み回数が10万回を超えた。"

    assert get_end_code_name(0xC201) == "slmp_end_code_c201"
    assert get_end_code_message(0xC201) == "The remote password status of the port used for communications is in the lock status."

    assert get_end_code_name(0xC810) == "slmp_end_code_c810"
    assert get_end_code_message(0xC810) == "Remote password authentication has failed when required. Set a correct password and retry."
    assert get_end_code_message(0xC811) == "Remote password authentication has failed when required. Set a correct password and retry after 1 minute."
    assert get_end_code_message(0xC814) == "Remote password authentication has failed when required. Set a correct password and retry after 60 minutes."
    assert get_end_code_message(0xC810, "ja") == "リモートパスワード認証が必要なアクセス時に，リモートパスワードのパスワード認証に失敗した。正しいパスワードを設定して再度実行してください。"

    assert get_end_code_name(0xCFBF) == "slmp_end_code_cfbf"
    assert get_end_code_message(0xCFBF) == "The simple CPU communication cannot be executed."


def test_unknown_and_remote_password_codes() -> None:
    assert get_end_code_name(0xDEAD) == "unknown_plc_end_code"
    assert get_end_code_message(0xDEAD) is None
    assert is_remote_password_end_code(0xC201)
    assert is_remote_password_end_code(0xC810)
    assert not is_remote_password_end_code(0x1080)


def test_slmp_error_end_code_helpers() -> None:
    error = SlmpError("SLMP error", end_code=0xC201)
    assert error.end_code_name == "slmp_end_code_c201"
    assert error.end_code_message == "The remote password status of the port used for communications is in the lock status."
    assert error.is_remote_password_error

    without_code = SlmpError("no end code")
    assert without_code.end_code_name is None
    assert without_code.end_code_message is None
    assert not without_code.is_remote_password_error
