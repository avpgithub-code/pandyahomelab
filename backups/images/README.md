# Image backups

Local copies of images that can no longer be pulled. Not in git (see `.gitignore`).

## minio-RELEASE.2025-09-07.tar.gz

- MinIO `RELEASE.2025-09-07T16-13-09Z`, image ID `sha256:69b2ec208575…`
- Pinned in `deployment/{ml,dl}/docker-compose.yml` as
  `minio/minio@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e`
- Saved 2026-09-23. Docker Hub returns 401 for `minio/minio`, so this may be the only copy.

### Restore

`docker load` restores the image but not its name or registry digest, so the
compose `@sha256:` reference will not match it. Tag it and point compose at the tag:

```sh
gunzip -c minio-RELEASE.2025-09-07.tar.gz | sudo docker load
sudo docker tag 69b2ec208575 minio/minio:RELEASE.2025-09-07T16-13-09Z
# In both compose files, replace the minio `image:` line with:
#   image: minio/minio:RELEASE.2025-09-07T16-13-09Z
#   pull_policy: never
```
