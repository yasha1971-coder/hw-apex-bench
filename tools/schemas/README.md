# Vendored CFF schema

`cff-1.2.0.schema.json` is the unmodified Citation File Format schema from tag
1.2.0, downloaded from the upstream project:
https://raw.githubusercontent.com/citation-file-format/citation-file-format/1.2.0/schema.json

SHA-256: `0b8d22140da702d766df318dcff3a91af2f39521298dcf36d76315fd99cc169b`.
Schema ID: `https://citation-file-format.github.io/1.2.0/schema.json`.
Local validation uses Draft 7 with format checks and makes no network requests.
Upstream license: CC BY 4.0, retained in [CFF-LICENSE](CFF-LICENSE.txt).
Attribution: the Citation File Format project, upstream tag 1.2.0, URL above.
The schema bytes are unmodified; this README and local integration are new.

[Zenodo subset schema](../../schemas/zenodo-v020.schema.json) is a strict local
contract for the metadata used by this benchmark; it is not the server's complete
deposit schema. Field definitions are based on primary documentation:
https://developers.zenodo.org/ and
https://help.zenodo.org/docs/github/describe-software/zenodo-json/ .
Passing local validation does not claim a Zenodo deposit has been submitted.
