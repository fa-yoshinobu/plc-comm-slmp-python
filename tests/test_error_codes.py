from slmp import (
    SlmpError,
    get_end_code_name,
    is_remote_password_end_code,
)


def test_end_code_names_are_code_derived() -> None:
    assert get_end_code_name(0x1080) == "slmp_end_code_1080"
    assert get_end_code_name(0xC201) == "slmp_end_code_c201"
    assert get_end_code_name(0xC810) == "slmp_end_code_c810"
    assert get_end_code_name(0xCFBF) == "slmp_end_code_cfbf"
    assert get_end_code_name(0xD913) == "slmp_end_code_d913"
    assert get_end_code_name(0xE504) == "slmp_end_code_e504"
    assert get_end_code_name(0xDEAD) == "slmp_end_code_dead"


def test_remote_password_codes() -> None:
    assert is_remote_password_end_code(0xC201)
    assert is_remote_password_end_code(0xC810)
    assert not is_remote_password_end_code(0x1080)


def test_slmp_error_end_code_helpers() -> None:
    error = SlmpError("SLMP error", end_code=0xC201)
    assert error.end_code_name == "slmp_end_code_c201"
    assert not hasattr(error, "end_code_message")
    assert error.is_remote_password_error

    without_code = SlmpError("no end code")
    assert without_code.end_code_name is None
    assert not hasattr(without_code, "end_code_message")
    assert not without_code.is_remote_password_error
