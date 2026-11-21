# Official technical references and adoption rules

This register is the starting reference set for PEOS. A link is a source to consult, not automatic approval to add a dependency. The repository's pinned version, local code and existing ADR remain the decision context.

| Area | Official source | Adopted practice for this platform | Boundary |
|---|---|---|---|
| Spring Modulith module boundaries (backend pin 2.1.2) | https://docs.spring.io/spring-modulith/reference/fundamentals.html ; https://docs.spring.io/spring-modulith/reference/verification.html | Declare application modules and named interfaces using the framework-supported package or root-type declaration; run ApplicationModules.verify() for module dependency and cycle verification. | Pin measured from app-java-v3/pom.xml at 8b1d2a82bf5c870d88ffc7d5d05e36bb06175c26. No framework upgrade is authorized by this inventory. |
| Spring Modulith events | https://docs.spring.io/spring-modulith/reference/events.html | Use the Event Publication Registry for transactional listener publications, lifecycle state, failure inspection and explicit recovery. | Do not add a second event bus or assume automatic retry semantics without checking the pinned version and local configuration. |
| Testcontainers PostgreSQL | https://github.com/testcontainers/testcontainers-java/blob/main/docs/modules/databases/postgres.md | Use real PostgreSQL containers for database-specific integration and concurrency tests where H2 or mocks cannot prove the behavior. | Test scope only; do not add a production dependency or use production data. |
| Android architecture | https://developer.android.com/topic/architecture/recommendations | Keep UI and data layers explicit; use repositories, screen-level ViewModels, UDF, Flow/StateFlow and lifecycle-aware state collection as appropriate. | Adapt to the current Kotlin/Compose code; no blanket rewrite or library mandate. |
| Playwright browser testing | https://playwright.dev/docs/best-practices | Test user-visible behavior, isolate tests, prefer role/label/text locators and rely on locator auto-wait/retryability. | Use against isolated acceptance/test data, never mutable production records. |
| Spring Boot availability | https://docs.spring.io/spring-boot/reference/actuator/endpoints.html | Keep liveness and readiness separate; external dependency failures must not automatically trigger liveness restarts. | Confirm health groups and Railway deployment behavior in this app before declaring an operational SLO. |
| Flyway versioned migrations | https://documentation.red-gate.com/fd/versioned-migrations-273973333.html | Treat applied versioned migrations as immutable history; roll corrections forward with a new migration. | Existing migration ownership and branch ordering remain governed by app-java-v3 policies. |
| GitHub Actions secure use | https://docs.github.com/en/actions/reference/security/secure-use | Prefer dependency lockfiles where supported; otherwise pin actions to verified full-length commit SHAs and minimize token permissions. | Recheck supported lockfile format and repository policy before changing the current SHA-pinned workflows. |
| Saleor AI and tools | https://docs.saleor.io/developer/ai | Distinguish documentation-only access, schema inspection and live store mutations; enforce least privilege and source/version pins. | Saleor is the commerce contract/reference. Do not add a parallel Saleor backend or let a live MCP token leak to tools. |

## Technology adoption gate

A proposal for a new tool must include: (1) the concrete gap in this repository, (2) existing framework/platform alternatives checked first, (3) official documentation for the exact target version, (4) upstream release and license, (5) compatibility and operational cost, (6) a bounded PoC where justified, (7) measurable acceptance criteria, and (8) an approved ADR. A name in the table above is not an adoption decision.

## Evidence rule

For every technical claim in a PR, record the repository commit SHA, file path or API endpoint, the upstream documentation URL and the exact tested version. If a source has not been checked against the pinned version, mark the claim as unverified rather than transferring behavior from a newer release.

| Object storage erasure / S3 versioning | https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjectVersions.html ; https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjects.html ; https://docs.aws.amazon.com/AmazonS3/latest/userguide/troubleshooting-versioning.html | For versioning-enabled or suspended buckets, a key-only delete is not proof of permanent version erasure; use version IDs and account for delete markers and retention. | Verify the actual provider, bucket versioning and Object Lock settings before choosing a permanent-erasure implementation. |
