"""The containers the hub's tests start (`hub_services`) leave no docker volume behind."""

import json

import pytest

from hub_services import DATA, _docker, linux_containers


def test_each_test_image_has_a_tmpfs_at_every_volume_it_declares():
    """A path an image declares as a VOLUME gets an anonymous volume unless something is
    mounted there; `DATA` names each one, so the tests mount a tmpfs at all of them."""
    if why := linux_containers():
        pytest.skip(why)
    for image, paths in DATA.items():
        try:
            declared = _docker("image", "inspect", "--format", "{{json .Config.Volumes}}", image, timeout=30)
        except RuntimeError:
            _docker("pull", image, timeout=600)
            declared = _docker("image", "inspect", "--format", "{{json .Config.Volumes}}", image, timeout=30)
        assert sorted(json.loads(declared) or {}) == sorted(paths), image
