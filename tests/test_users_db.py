
import pytest

from storage.users_db import (
    authenticate_user,
    check_password,
    create_user,
    find_active_user,
    hash_password,
    list_users,
    reset_user_password,
    set_user_active,
    set_user_role,
)


def test_password_hash_is_not_the_password_and_verifies():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$2")           # bcrypt
    assert check_password("correct horse battery staple", hashed) is True
    assert check_password("wrong", hashed) is False


def test_the_same_password_hashes_differently_each_time():
    assert hash_password("same") != hash_password("same")


def test_create_and_authenticate(temp_db):
    create_user("alice", "correct-horse-battery", "scientist")
    assert authenticate_user("alice", "correct-horse-battery") == "scientist"
    assert authenticate_user("alice", "wrong") is None
    assert authenticate_user("nobody", "correct-horse-battery") is None


def test_usernames_are_stripped_on_create_and_lookup(temp_db):
    create_user("  bob  ", "a-valid-passphrase", "user")
    assert authenticate_user("bob", "a-valid-passphrase") == "user"
    assert authenticate_user("  bob  ", "a-valid-passphrase") == "user"


def test_duplicate_usernames_are_rejected(temp_db):
    import sqlite3
    create_user("alice", "a-valid-passphrase", "user")
    with pytest.raises(sqlite3.IntegrityError):
        create_user("alice", "another-passphrase", "admin")


@pytest.mark.parametrize("role", ["superuser", "", "ADMIN", None])
def test_an_invalid_role_is_rejected(temp_db, role):
    with pytest.raises(ValueError, match="Role must be"):
        create_user("carol", "a-valid-passphrase", role)


def test_an_empty_username_is_rejected(temp_db):
    with pytest.raises(ValueError, match="Username is required"):
        create_user("   ", "a-valid-passphrase", "user")


def test_a_deactivated_user_cannot_authenticate(temp_db):
    create_user("dave", "a-valid-passphrase", "user")
    set_user_active("dave", False)
    assert authenticate_user("dave", "a-valid-passphrase") is None
    assert find_active_user("dave") is None
    set_user_active("dave", True)
    assert authenticate_user("dave", "a-valid-passphrase") == "user"


def test_role_changes_take_effect(temp_db):
    create_user("erin", "a-valid-passphrase", "user")
    set_user_role("erin", "admin")
    assert authenticate_user("erin", "a-valid-passphrase") == "admin"


def test_set_user_role_rejects_an_invalid_role(temp_db):
    create_user("erin", "a-valid-passphrase", "user")
    with pytest.raises(ValueError):
        set_user_role("erin", "root")


def test_password_reset_invalidates_the_old_password(temp_db):
    create_user("frank", "old-password", "user")
    reset_user_password("frank", "new-password")
    assert authenticate_user("frank", "old-password") is None
    assert authenticate_user("frank", "new-password") == "user"


def test_password_reset_requires_a_password(temp_db):
    create_user("frank", "old-password", "user")
    with pytest.raises(ValueError, match="Password is required"):
        reset_user_password("frank", "")


def test_list_users_never_returns_a_password_hash(temp_db):
    create_user("gina", "a-valid-passphrase", "admin")
    users = list_users()
    assert users and "password_hash" not in users[0]
    assert set(users[0]) == {"id", "username", "role", "is_active", "created_at"}


def test_list_users_is_sorted_by_username(temp_db):
    for name in ("zoe", "adam", "mia"):
        create_user(name, "a-valid-passphrase", "user")
    assert [u["username"] for u in list_users()] == ["adam", "mia", "zoe"]



from storage.users_db import (  # noqa: E402
    MAX_PASSWORD_BYTES,
    MIN_PASSWORD_LENGTH,
    validate_password,
)


def test_the_minimum_length_is_twelve():
    assert MIN_PASSWORD_LENGTH == 12


@pytest.mark.parametrize("password", ["", "short", "elevenchars", None])
def test_passwords_below_the_minimum_are_rejected(password):
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_password(password)


def test_a_twelve_character_password_is_accepted():
    validate_password("a" * MIN_PASSWORD_LENGTH)


def test_a_long_passphrase_with_no_special_characters_is_accepted():
    validate_password("correct horse battery staple")


def test_passwords_beyond_bcrypts_limit_are_rejected_not_truncated():
    with pytest.raises(ValueError, match="72 bytes"):
        validate_password("x" * (MAX_PASSWORD_BYTES + 1))


def test_the_byte_limit_counts_bytes_not_characters():
    with pytest.raises(ValueError, match="72 bytes"):
        validate_password("ü" * 40)          # 80 bytes, 40 characters


def test_create_user_enforces_the_policy(temp_db):
    with pytest.raises(ValueError, match="at least 12 characters"):
        create_user("hank", "short", "user")
    assert list_users() == []


def test_password_reset_enforces_the_policy(temp_db):
    create_user("hank", "a-valid-passphrase", "user")
    with pytest.raises(ValueError, match="at least 12 characters"):
        reset_user_password("hank", "short")
    assert authenticate_user("hank", "a-valid-passphrase") == "user"
