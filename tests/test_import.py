def test_package_importable():
    import tay
    assert tay.__version__ == "0.1.0"
