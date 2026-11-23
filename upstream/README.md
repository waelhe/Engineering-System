# Upstream EGM baseline

The directory upstream/egm is a Git submodule pinned to the exact v0.1.1 source commit recorded in egm.lock.json.

Do not edit the submodule checkout in place. Local extensions and overlays belong in extensions/. The build tool assembles an integrated runtime package from this pinned source plus reviewed local overlays.

The upstream project is Apache-2.0. Preserve its LICENSE and notices when redistributing the assembled package. The project explicitly says it is not an officially supported Google product.
