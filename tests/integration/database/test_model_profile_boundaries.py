import pytest

from proseforge.infrastructure.database.repositories.model_profile import SqlAlchemyModelProfileRepository


@pytest.mark.asyncio
async def test_model_profiles_are_owner_scoped(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyModelProfileRepository(session)
        owned = await repository.create("profile-owner-a", "Writer A", {"provider": "openai", "model": "a"})
        await repository.create("profile-owner-b", "Writer B", {"provider": "openai", "model": "b"})
        await session.commit()

    async with session_factory() as session:
        repository = SqlAlchemyModelProfileRepository(session)
        owner_a = await repository.list_for_user("profile-owner-a")
        owner_b = await repository.list_for_user("profile-owner-b")

        assert [profile["id"] for profile in owner_a] == [owned["id"]]
        assert owner_b[0]["id"] != owned["id"]
        assert await repository.get_owned("profile-owner-b", owned["id"]) is None


@pytest.mark.asyncio
async def test_model_profile_owner_must_match_before_mutation(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyModelProfileRepository(session)
        owned = await repository.create("profile-update-owner", "Writer", {"provider": "openai", "model": "old"})
        await session.commit()

    async with session_factory() as session:
        repository = SqlAlchemyModelProfileRepository(session)
        assert await repository.get_owned("profile-other-owner", owned["id"]) is None
