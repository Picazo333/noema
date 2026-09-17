# Artifacts, Storage, and Provenance

Artifacts are promoted/material objects worth persistent identity. Not every repository file becomes an Artifact.

`StorageRef` separates logical reference from physical provider. RC0 validates `repo`, `file`, and `github` schemes and reserves future schemes such as `drive`, `eidema`, and `obsidian`.

Minimal provenance records the producing activity, actor/executor, source/input references, time, and integrity/version when appropriate. No provenance graph database is required.
