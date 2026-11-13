# Architecture and decisions

## Purpose

A runnable YouTube-style application for the StackBridge / Gufo test assignment. The primary scenario is registration → upload with progress → background processing → playback → like and comment. The employer specification is retained in requirements.txt and the original DOCX in this folder.

## Selected approach

A modular FastAPI monolith serves the JSON API and a buildless ES-module frontend on one origin. PostgreSQL stores metadata, opaque sessions and a durable processing queue. A separate Python worker transcodes uploads with FFmpeg. Private S3-compatible storage holds originals, processed MP4 and JPEG thumbnails. Docker Compose starts the application, PostgreSQL, storage, initialization and worker.

This is the implementation choice made by the assistant under the user's instruction to proceed. A separate SPA build, Redis/Celery and Kubernetes would add moving parts without improving the assessed scenario. A filesystem-only video store would not meet the object-storage requirement. A PostgreSQL-backed queue uses row locks and expiring leases, avoiding another infrastructure dependency.

## Data and boundaries

Users have unique case-insensitive handles and one channel each. Videos belong to a user, have public/private visibility and independent upload/processing and moderation states. Grants allow explicitly selected users to view a private video. Subscriptions, likes and playlist items have database uniqueness constraints. Comments and reports reference videos. Playlists belong to users and never bypass video authorization. Moderation actions are audited.

Authentication uses random opaque HttpOnly session cookies, hashed tokens at rest, expiry, logout revocation and per-session CSRF tokens. Passwords use salted scrypt. Registration never accepts a role; only administrators change roles. Mutating requests verify origin and CSRF. Authentication throttling persists in PostgreSQL.

The browser never receives an S3 credential or public object URL. API endpoints authorize every media request, proxy S3 objects and support a single HTTP byte range. Private responses use no-store. Moderators can inspect reported/private content for moderation; this explicit exception is documented in the API and UI, and they cannot grant viewing rights. Administrators cannot be created through public signup.

## Upload and processing

Create metadata, PUT raw bytes with XMLHttpRequest progress, persist the source to S3 and queue the record. Enforce upload size while receiving bytes and limit request bodies before parsing JSON. Filename is never an object key. Each receiving attempt owns a lease, refreshes a heartbeat and writes an immutable source key. Only that lease may publish the source or reset a failed upload. The worker claims queued/stale work using FOR UPDATE SKIP LOCKED, stores a lease, validates with ffprobe and creates H.264/AAC MP4 plus thumbnail. Each worker attempt writes immutable output keys; only a lease-conditional database update publishes them. A stale attempt cannot overwrite the current objects and its unpublished outputs are discarded. Failures are visible to the owner, bounded retries handle transient failures, and an expired lease recovers an interrupted worker. Transcoding only permits local input protocols and has a timeout. Scratch files are temporary.

## Visual direction

Faithful YouTube layout: fixed white top bar, red play mark, central search, compact left navigation, topic chips and a responsive 16:9 thumbnail grid. Watch page uses a large black player with a recommendation rail; channel pages have a banner, avatar and tabs. No marketing hero. Palette: white #ffffff, canvas #f9f9f9, primary #0f0f0f, secondary #606060, red #ff0033, blue #065fd4. Arial/system sans body with a condensed bold wordmark. Motion only for feedback. The red play mark and familiar information density are the visual signature.

## Scope

Home, search, watch, channel, subscription feed, upload, authentication, owner studio, playlists, grant editing, moderation and admin roles. Seeded users and locally bundled demo video assets make first-run inspection possible without third-party media requests. Tests cover privacy, privilege escalation, CSRF, media ranges, ownership, invalid uploads and the full video pipeline.

The single-node deployment is intended for evaluation. No recommendations ML, live streaming, adaptive HLS, email recovery, malware scanner or multi-node high availability is claimed. Production exposure requires TLS and secure cookies, backup policy and operational capacity planning.

