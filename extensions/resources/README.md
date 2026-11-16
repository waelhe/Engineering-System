# EGM Engineering System runtime resources

The build tool assembles these resources with the pinned upstream EGM package. The canonical editable policies remain under docs/policies and docs/architecture; the package builder copies them into the runtime bundle to avoid maintaining duplicate source files.

The local execution charter replaces only the generated package's shared execution instructions. Upstream files are not edited.


The package builder injects an explicit charter-loading directive into a temporary exported copy of upstream `egm-review`, so direct review invocation loads the local runtime authority. The staged copy comes from the pinned Git object; the upstream submodule source remains unchanged.
