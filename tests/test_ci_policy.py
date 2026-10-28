"""Check that editing or submitting a PR never grants publishing credentials."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import ruamel.yaml


def test_publishing_identity_and_permissions():
    data = ruamel.yaml.YAML(typ='safe').load(Path('.github/workflows/build-pkgs.yml'))
    assert data['permissions'] == {'contents': 'read'}
    build = data['jobs']['build']
    assert 'environment' not in build
    publish = data['jobs']['publish']
    assert publish['needs'] == 'build'
    assert publish['environment'] == 'production'
    assert publish['permissions']['id-token'] == 'write'
    assert "github.ref == 'refs/heads/main'" in publish['if']
    assert "github.event_name != 'pull_request'" in publish['if']


@pytest.mark.parametrize('event,ref,repo', [
    ('pull_request', 'refs/pull/1/merge', 'gbionics/gb-conda-forge-staging-recipes'),
    ('pull_request_target', 'refs/heads/main', 'gbionics/gb-conda-forge-staging-recipes'),
    ('push', 'refs/heads/topic', 'gbionics/gb-conda-forge-staging-recipes'),
    ('push', 'refs/heads/main', 'fork/conda-forge-staging-recipes'),
])
def test_upload_refuses_untrusted_runs(event, ref, repo):
    env = dict(os.environ, GITHUB_ACTIONS='true', GITHUB_EVENT_NAME=event,
               GITHUB_REF=ref, GITHUB_REPOSITORY=repo)
    result = subprocess.run([sys.executable, 'scripts/upload.py'], env=env,
                            text=True, capture_output=True)
    assert result.returncode != 0
    assert 'Uploads require a main-branch' in result.stderr


def test_upload_selects_channel_artifacts_and_excludes_failed_builds(tmp_path, monkeypatch):
    import runpy
    script = Path('scripts/upload.py').resolve()
    for subdir in ('linux-64', 'linux-aarch64', 'noarch', 'broken'):
        directory = tmp_path / 'output' / subdir
        directory.mkdir(parents=True)
        (directory / 'test-1.0-0.conda').touch()
    monkeypatch.chdir(tmp_path)
    for name, value in {
        'GITHUB_ACTIONS': 'true', 'GITHUB_EVENT_NAME': 'push',
        'GITHUB_REF': 'refs/heads/main',
        'GITHUB_REPOSITORY': 'gbionics/gb-conda-forge-staging-recipes',
    }.items():
        monkeypatch.setenv(name, value)
    calls = []
    monkeypatch.setattr(subprocess, 'run', lambda args, **kwargs: calls.append(args))
    runpy.run_path(str(script), run_name='__main__')
    assert len(calls) == 1
    artifacts = [arg for arg in calls[0] if arg.endswith('.conda')]
    assert set(artifacts) == {
        'output/linux-64/test-1.0-0.conda', 'output/linux-aarch64/test-1.0-0.conda',
        'output/noarch/test-1.0-0.conda',
    }


def test_native_ci_matrix_and_artifact_merge():
    data = ruamel.yaml.YAML(typ='safe').load(Path('.github/workflows/build-pkgs.yml'))
    build = data['jobs']['build']
    assert {entry['platform']: entry['runner'] for entry in build['strategy']['matrix']['include']} == {
        'linux-64': 'ubuntu-24.04', 'linux-aarch64': 'ubuntu-24.04-arm',
    }
    assert build['strategy']['fail-fast'] is False
    download = next(step for step in data['jobs']['publish']['steps']
                    if step.get('uses', '').startswith('actions/download-artifact@'))
    assert download['with']['merge-multiple'] is True


@pytest.mark.parametrize('platform,expected', [
    ('linux-64', {'linux-64', 'noarch'}),
    ('linux-aarch64', {'linux-aarch64'}),
])
def test_collect_artifacts_avoids_duplicate_noarch(tmp_path, platform, expected):
    script = Path('scripts/collect_artifacts.py').resolve()
    for subdir in ('linux-64', 'linux-aarch64', 'noarch', 'broken'):
        directory = tmp_path / 'output' / subdir
        directory.mkdir(parents=True)
        (directory / 'test-1.0-0.conda').touch()
    subprocess.run([sys.executable, str(script), platform], cwd=tmp_path, check=True)
    assert {p.parent.name for p in (tmp_path / 'artifacts').glob('*/*.conda')} == expected
