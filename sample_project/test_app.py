from app import divide, format_result


def test_divide():
    assert divide(8, 2) == 4


def test_format_result():
    assert format_result(3.5) == "Result: 3.5"