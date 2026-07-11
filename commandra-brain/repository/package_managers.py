"""
Package manager detection -- goes beyond a single framework signal file to
say precisely which package manager(s) govern a repository and what that
implies for the Tool System (which command to run to install/build/test).
"""

from __future__ import annotations

from dataclasses import dataclass

from repository.scanner import RepoFile

# filename -> (package manager id, ecosystem, install command)
_SIGNALS: list[tuple[str, str, str, str]] = [
    ("pnpm-lock.yaml", "pnpm", "node", "pnpm install"),
    ("package-lock.json", "npm", "node", "npm install"),
    ("yarn.lock", "yarn", "node", "yarn install"),
    ("bun.lockb", "bun", "node", "bun install"),
    ("package.json", "npm", "node", "npm install"),
    ("requirements.txt", "pip", "python", "pip install -r requirements.txt"),
    ("pyproject.toml", "pip", "python", "pip install -e ."),
    ("Pipfile", "pipenv", "python", "pipenv install"),
    ("poetry.lock", "poetry", "python", "poetry install"),
    ("uv.lock", "uv", "python", "uv sync"),
    ("Cargo.toml", "cargo", "rust", "cargo build"),
    ("go.mod", "go modules", "go", "go mod download"),
    ("pom.xml", "maven", "java", "mvn install"),
    ("build.gradle", "gradle", "java/kotlin", "gradle build"),
    ("build.gradle.kts", "gradle", "java/kotlin", "gradle build"),
    ("Gemfile", "bundler", "ruby", "bundle install"),
    ("composer.json", "composer", "php", "composer install"),
    ("pubspec.yaml", "pub", "dart/flutter", "flutter pub get"),
    ("mix.exs", "mix", "elixir", "mix deps.get"),
]


@dataclass
class PackageManagerInfo:
    name: str
    ecosystem: str
    install_command: str
    lockfile: str


def detect_package_managers(files: list[RepoFile]) -> list[PackageManagerInfo]:
    names = {f.path.split("/")[-1] for f in files}
    found: list[PackageManagerInfo] = []
    seen_ecosystems: set[str] = set()

    # Prefer the most specific lockfile per ecosystem (e.g. pnpm-lock over package.json).
    for filename, manager, ecosystem, install_cmd in _SIGNALS:
        if filename not in names:
            continue
        if ecosystem in seen_ecosystems and filename in {"package.json", "requirements.txt", "pyproject.toml"}:
            continue
        found.append(PackageManagerInfo(name=manager, ecosystem=ecosystem, install_command=install_cmd, lockfile=filename))
        seen_ecosystems.add(ecosystem)

    return found
