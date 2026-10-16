# Releasing

A release publishes one version everywhere: the Python package `contraagent` to
PyPI, and `@contraagent/api`, `@contraagent/elements` and `@contraagent/ui` to npm.
The push of a tag starts it, and `.github/workflows/release.yml` does the rest.
Both registries take the files through Trusted Publishing, so no token is stored
in the repository's secrets.

## Release a version

The version is in four files, and they must agree: `pyproject.toml` and the
`package.json` of each of the three packages in `web/packages/`. The tag is the
version itself, with no `v` (`0.2.0`).

1. Set the version in the four files, if it changed since the last release.
2. Write the changelog section from the fragments in `changelog.d/`:

   ```
   uv run towncrier build --version X.Y.Z
   ```

3. Commit the version and `CHANGELOG.md` on `main`, and push it.
4. Tag that commit and push the tag:

   ```
   git tag X.Y.Z && git push origin X.Y.Z
   ```

The workflow checks that the tag, the four versions and the dependencies between
the npm packages all name `X.Y.Z`, and that `CHANGELOG.md` has its section. It
runs every job of `ci.yml`, builds the sdist and the wheel (`uv build`, `twine
check`) and the npm tarballs (`pnpm tarballs:registry`). Then it publishes to PyPI
and to npm, in the order api, elements, ui, and creates the GitHub release with
that section as its notes and the Python files attached. The `pypi` and `npm`
environments wait for the owner's approval.

A dry run checks the same steps with nothing released. Start the workflow by hand
(Actions, Release, Run workflow) with `testpypi` on: the Python package goes to
TestPyPI, `npm publish --dry-run` checks each tarball, and no GitHub release is
made. Before `towncrier build`, the missing changelog section is only a warning.

## One-time setup

The owner of the repository does these steps by hand, once, before the first
release.

1. On PyPI, add a pending publisher for the project `contraagent`: owner
   `t-tani`, repository `contraagent`, workflow `release.yml`, environment
   `pypi`.
2. On TestPyPI, add the same pending publisher with the environment `testpypi`.
3. In the repository settings on GitHub, create the environments `pypi`, `npm`
   and `testpypi`. `pypi` and `npm` accept only version tags and need the owner's
   approval; `testpypi` accepts runs from `main`.
4. Publish each npm package once from a local tarball, because npm sets a Trusted
   Publisher only on a package that exists. Log in with `npm login` as a member of
   the `contraagent` organization, then in `web/`:

   ```
   pnpm install
   pnpm tarballs:registry
   npm publish tarballs/contraagent-api-X.Y.Z.tgz --access public
   npm publish tarballs/contraagent-elements-X.Y.Z.tgz --access public
   npm publish tarballs/contraagent-ui-X.Y.Z.tgz --access public
   ```

5. On npmjs.com, in the settings of each of the three packages, add a Trusted
   Publisher: GitHub Actions, owner `t-tani`, repository `contraagent`, workflow
   `release.yml`, environment `npm`.

The workflow leaves a version that is on npm already as it is, so it releases
the version from step 4 to PyPI and GitHub and skips it on npm. That version has
no provenance on npm; every later one has.
