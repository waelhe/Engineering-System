# W2 — Source-bound Maven and Spring Modulith boundaries

**Snapshot:** 2026-11-15  
**Backend:** `waelhe/app-java-v3/main` at `8b1d2a82bf5c870d88ffc7d5d05e36bb06175c26`  
**Root POM blob:** `0d53d259fd440a88e3517c34e7e6703420171439`

## Purpose and method

This is a source-derived inventory, not a new architecture decision. It was built from the pinned root Maven POM, the 30 child POMs, Spring Modulith descriptors, named-interface declarations, the application bootstrap, architecture tests and accepted ADRs. Each artifact is linked by its Git blob SHA in `registry/peos/app-java-v3.module-boundaries.json`.

Maven dependencies and Spring Modulith `allowedDependencies` are separate graphs. A Maven artifact dependency is not assumed to prove a Java-level module API dependency. Domain ownership remains `not_adjudicated`; names, POM boundaries and package annotations alone do not establish all business responsibilities.

## Measured topology

| Fact | Count |
|---|---:|
| Maven reactor artifacts | 30 |
| Logical Spring Modulith package modules | 30 |
| Bounded-context packages | 26 |
| App/admin/config composition and support packages | 3 |
| Root-type `@ApplicationModule` declarations | 5 |
| Standalone Edge BFF outside root Modulith verification | 1 |

The equal 30/30 counts are not a one-to-one mapping:

- `marketplace-shared` and `marketplace-platform-infra` jointly supply the logical `shared` module. The latter contributes the `shared-config`, `shared-email`, `shared-jpa` and `shared-security` named-interface packages under `com.marketplace.shared.*`.
- The `marketplace-app` Maven artifact contains three logical packages: `com.marketplace.app`, `com.marketplace.admin` and `com.marketplace.config`.
- `marketplace-edge` is a separate Spring Boot Gateway BFF, has no internal Maven artifact dependencies, and is explicitly outside `MarketplaceApplication` Modulith verification.

## Source-observed boundary rules

- The logical `shared` application module declares `allowedDependencies = {}`, i.e. a closed module with no allowed application-module dependencies.
- Five declarations place `@ApplicationModule` on a root type rather than `package-info.java`: `availability`, `disputes`, `ledger`, `notifications`, `provider`.
- `messaging` and `realestate` explicitly allow `catalog :: catalog-spi`. The app/admin composition packages also declare selected domain SPIs. The inventory preserves those declarations and does not remove or widen dependencies.
- The application composition package consumes selected domain interfaces; that does not make it the owner of those domains.
- The registry deliberately leaves domain ownership unadjudicated.

## Verification evidence and limits

The application root is `com.marketplace.MarketplaceApplication` (`@Modulithic`). `ModulithVerificationTest.verifyModulesAndWriteDocs()` calls `ApplicationModules.of(MarketplaceApplication.class).verify()` and then the Spring Modulith `Documenter`. `ModulithGuardReadinessTest` fails the build on JDK 26+ rather than allowing the architecture test to be silently skipped; the repository pins Java 25. Architecture and generated-documentation test sources are source-bound in the registry.

The backend main CI run for the audited SHA is [#43621271125](https://github.com/waelhe/app-java-v3/actions/runs/43621271125), overall conclusion **success**. This is not a separate human review, deployment proof or launch-readiness certification. W1's production and telemetry gaps remain open.

## Documentation drift

1. `docs/architecture/ARCHITECTURE.md` says all module declarations are in `package-info.java`, while five declarations are on root types.
2. The guide simplifies allowed dependencies to shared-only; the current `messaging` and `realestate` package descriptors explicitly allow `catalog :: catalog-spi`.
3. `SYSTEM.md` §5 describes 24 bounded contexts and a package-info-only convention; the pinned source inventory now has 26 bounded-context packages and five type-level declarations.
4. Maven / Modulith topology is many-to-many despite the numerical 30/30 count.

These differences are recorded with source SHAs; this PEOS change does not modify backend code, ADRs, migrations, production settings or backend architecture documents.

## Official framework basis

The backend root POM pins Spring Modulith **2.1.2**. The official [Fundamentals](https://docs.spring.io/spring-modulith/reference/fundamentals.html) and [Verification](https://docs.spring.io/spring-modulith/reference/verification.html) documentation defines application-module declarations, named interfaces and `ApplicationModules.verify()`. The registry binds the local implementation to the exact backend SHA and does not authorize a framework upgrade.
