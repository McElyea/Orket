[CmdletBinding()]
param(
    [string]$UserName = "Jon",
    [string]$PolicyName = "OrketNorthstarWork",
    [string]$BucketPrefix = "orket-northstar-*",
    [string]$BackupRoot = "workspace/trusted_terraform_live_setup/iam_permission_update",
    [switch]$DryRun,
    [switch]$ExecuteIamMutation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
}

function Resolve-OutputRoot {
    param([string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return (Join-Path (Resolve-RepoRoot) $PathValue)
}

function New-RunBackupDirectory {
    param([string]$Root)

    $resolvedRoot = Resolve-OutputRoot -PathValue $Root
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
    $directory = Join-Path $resolvedRoot "run-$stamp-$suffix"
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    return $directory
}

function Write-TextFile {
    param(
        [string]$Path,
        [string]$Text
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText($Path, $Text, $utf8NoBom)
}

function ConvertTo-StringArray {
    param([object]$Value)

    return @($Value) |
        Where-Object { $null -ne $_ -and -not [string]::IsNullOrWhiteSpace([string]$_) } |
        ForEach-Object { [string]$_ }
}

function Get-StringArrayCount {
    param([object]$Value)

    return @(ConvertTo-StringArray -Value $Value).Count
}

function Format-StringArrayOrNone {
    param([object]$Value)

    $items = @(ConvertTo-StringArray -Value $Value)
    if ($items.Count -eq 0) {
        return "<none>"
    }
    return ($items -join ", ")
}

function ConvertTo-SafeFileName {
    param([string]$Value)

    return ($Value -replace "[^A-Za-z0-9_.@+=,-]", "_")
}

function Format-CommandArgument {
    param([string]$Value)

    if ($Value -match "^[A-Za-z0-9_./:=,@*+\-]+$") {
        return $Value
    }
    return "'" + $Value.Replace("'", "''") + "'"
}

function Format-AwsCommand {
    param([string[]]$Arguments)

    $parts = @("aws")
    foreach ($argument in $Arguments) {
        $parts += (Format-CommandArgument -Value $argument)
    }
    return ($parts -join " ")
}

function ConvertTo-AwsFileUri {
    param([string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path).Path.Replace("\", "/")
    return "file://$resolved"
}

function ConvertFrom-JsonText {
    param(
        [string]$Text,
        [string]$Description
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        throw "$Description returned empty output."
    }

    try {
        return ($Text | ConvertFrom-Json)
    }
    catch {
        throw "$Description returned non-JSON output: $($_.Exception.Message)"
    }
}

function Invoke-AwsCli {
    param(
        [string[]]$Arguments,
        [string]$OutputPath = ""
    )

    $commandText = Format-AwsCommand -Arguments $Arguments
    Write-Host "> $commandText"

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & aws @Arguments 1> $stdoutPath 2> $stderrPath
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        $exitCode = $LASTEXITCODE
        $stdout = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue
        $stderr = Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue

        if ($OutputPath) {
            Write-TextFile -Path $OutputPath -Text ([string]$stdout)
        }

        if ($exitCode -ne 0) {
            $errorPath = ""
            if ($OutputPath) {
                $errorPath = "$OutputPath.stderr.txt"
                Write-TextFile -Path $errorPath -Text ([string]$stderr)
            }
            $detail = ([string]$stderr).Trim()
            if ([string]::IsNullOrWhiteSpace($detail)) {
                $detail = ([string]$stdout).Trim()
            }
            if ($errorPath) {
                throw "AWS CLI failed with exit code $exitCode. Command: $commandText. Stderr saved to $errorPath. $detail"
            }
            throw "AWS CLI failed with exit code $exitCode. Command: $commandText. $detail"
        }

        return [pscustomobject]@{
            Command = $commandText
            Stdout = [string]$stdout
            Stderr = [string]$stderr
            ExitCode = $exitCode
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function New-OrketNorthstarPolicyDocument {
    param([string]$BucketNamePrefix)

    if ([string]::IsNullOrWhiteSpace($BucketNamePrefix)) {
        throw "BucketPrefix must not be empty."
    }
    if ($BucketNamePrefix -match "^arn:") {
        throw "BucketPrefix must be a bucket name or wildcard pattern, not an ARN."
    }
    if ($BucketNamePrefix -match "/") {
        throw "BucketPrefix must not include an object path."
    }

    $bucketArn = "arn:aws:s3:::$BucketNamePrefix"
    $objectArn = "arn:aws:s3:::$BucketNamePrefix/*"

    return [ordered]@{
        Version = "2012-10-17"
        Statement = @(
            [ordered]@{
                Sid = "BedrockInvoke"
                Effect = "Allow"
                Action = @(
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                )
                Resource = "*"
            },
            [ordered]@{
                Sid = "BedrockReadPreflight"
                Effect = "Allow"
                Action = @(
                    "bedrock:ListFoundationModels",
                    "bedrock:GetFoundationModel",
                    "bedrock:GetFoundationModelAvailability",
                    "bedrock:ListInferenceProfiles",
                    "bedrock:GetInferenceProfile"
                )
                Resource = "*"
            },
            [ordered]@{
                Sid = "ServiceQuotasReadPreflight"
                Effect = "Allow"
                Action = @(
                    "servicequotas:ListServices",
                    "servicequotas:ListServiceQuotas",
                    "servicequotas:GetServiceQuota",
                    "servicequotas:ListAWSDefaultServiceQuotas",
                    "servicequotas:GetAWSDefaultServiceQuota"
                )
                Resource = "*"
            },
            [ordered]@{
                Sid = "CallerIdentity"
                Effect = "Allow"
                Action = @("sts:GetCallerIdentity")
                Resource = "*"
            },
            [ordered]@{
                Sid = "NorthstarBucketPermissions"
                Effect = "Allow"
                Action = @(
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:GetBucketTagging",
                    "s3:PutBucketTagging",
                    "s3:GetBucketPublicAccessBlock",
                    "s3:PutBucketPublicAccessBlock"
                )
                Resource = @($bucketArn)
            },
            [ordered]@{
                Sid = "NorthstarObjectPermissions"
                Effect = "Allow"
                Action = @(
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                )
                Resource = @($objectArn)
            }
        )
    }
}

function Save-PolicyDocument {
    param(
        [object]$PolicyDocument,
        [string]$OutputPath
    )

    $prettyJson = $PolicyDocument | ConvertTo-Json -Depth 20
    $compressedJson = $PolicyDocument | ConvertTo-Json -Depth 20 -Compress
    if ($compressedJson.Length -gt 6144) {
        throw "Generated policy has $($compressedJson.Length) non-whitespace characters, exceeding the 6144 customer-managed IAM policy limit."
    }
    Write-TextFile -Path $OutputPath -Text ($prettyJson + [Environment]::NewLine)
    return $compressedJson.Length
}

function ConvertTo-CompressedJson {
    param([object]$Value)

    return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

function Save-CurrentInventory {
    param(
        [string]$TargetUserName,
        [string]$Directory
    )

    $listUserPolicies = Invoke-AwsCli -Arguments @("iam", "list-user-policies", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "01-list-user-policies.json")
    $inlinePolicyNames = ConvertTo-StringArray -Value (ConvertFrom-JsonText -Text $listUserPolicies.Stdout -Description "list-user-policies").PolicyNames

    foreach ($inlinePolicyName in $inlinePolicyNames) {
        $safeName = ConvertTo-SafeFileName -Value $inlinePolicyName
        Invoke-AwsCli -Arguments @("iam", "get-user-policy", "--user-name", $TargetUserName, "--policy-name", $inlinePolicyName, "--output", "json") -OutputPath (Join-Path $Directory "02-inline-user-policy-$safeName.json") | Out-Null
    }

    $attachedPolicies = Invoke-AwsCli -Arguments @("iam", "list-attached-user-policies", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "03-list-attached-user-policies.json")
    $groups = Invoke-AwsCli -Arguments @("iam", "list-groups-for-user", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "04-list-groups-for-user.json")
    $caller = Invoke-AwsCli -Arguments @("sts", "get-caller-identity", "--output", "json") -OutputPath (Join-Path $Directory "05-get-caller-identity.json")

    $attachedPayload = ConvertFrom-JsonText -Text $attachedPolicies.Stdout -Description "list-attached-user-policies"
    $groupPayload = ConvertFrom-JsonText -Text $groups.Stdout -Description "list-groups-for-user"
    $callerPayload = ConvertFrom-JsonText -Text $caller.Stdout -Description "get-caller-identity"

    return [pscustomobject]@{
        InlinePolicyNames = $inlinePolicyNames
        AttachedPolicyArns = ConvertTo-StringArray -Value (@($attachedPayload.AttachedPolicies) | ForEach-Object { $_.PolicyArn })
        GroupNames = ConvertTo-StringArray -Value (@($groupPayload.Groups) | ForEach-Object { $_.GroupName })
        AccountId = [string]$callerPayload.Account
        CallerArn = [string]$callerPayload.Arn
    }
}

function Find-CustomerManagedPolicyArn {
    param(
        [string]$TargetPolicyName,
        [string]$Directory
    )

    $policies = Invoke-AwsCli -Arguments @("iam", "list-policies", "--scope", "Local", "--output", "json") -OutputPath (Join-Path $Directory "06-list-local-managed-policies.json")
    $payload = ConvertFrom-JsonText -Text $policies.Stdout -Description "list-policies"
    $matches = @($payload.Policies | Where-Object { $_.PolicyName -eq $TargetPolicyName })
    if (@($matches).Count -gt 1) {
        throw "More than one customer-managed policy named $TargetPolicyName was returned; refusing to choose implicitly."
    }
    if (@($matches).Count -eq 0) {
        return ""
    }
    return [string]$matches[0].Arn
}

function Ensure-CustomerManagedPolicy {
    param(
        [string]$ExistingPolicyArn,
        [string]$TargetPolicyName,
        [object]$PolicyDocument,
        [string]$PolicyDocumentPath,
        [string]$Directory
    )

    $policyDocumentUri = ConvertTo-AwsFileUri -Path $PolicyDocumentPath

    if ([string]::IsNullOrWhiteSpace($ExistingPolicyArn)) {
        $created = Invoke-AwsCli -Arguments @("iam", "create-policy", "--policy-name", $TargetPolicyName, "--policy-document", $policyDocumentUri, "--output", "json") -OutputPath (Join-Path $Directory "07-create-policy.json")
        $payload = ConvertFrom-JsonText -Text $created.Stdout -Description "create-policy"
        return [string]$payload.Policy.Arn
    }

    $versions = Invoke-AwsCli -Arguments @("iam", "list-policy-versions", "--policy-arn", $ExistingPolicyArn, "--output", "json") -OutputPath (Join-Path $Directory "07-list-policy-versions-before-update.json")
    $versionPayload = ConvertFrom-JsonText -Text $versions.Stdout -Description "list-policy-versions"
    $versionList = @($versionPayload.Versions)
    $defaultVersion = @($versionList | Where-Object { $_.IsDefaultVersion } | Select-Object -First 1)
    if (@($defaultVersion).Count -ne 1) {
        throw "Policy $ExistingPolicyArn did not return exactly one default version."
    }

    $defaultVersionId = [string]$defaultVersion[0].VersionId
    $currentDefault = Invoke-AwsCli -Arguments @("iam", "get-policy-version", "--policy-arn", $ExistingPolicyArn, "--version-id", $defaultVersionId, "--output", "json") -OutputPath (Join-Path $Directory "08-get-current-default-policy-version.json")
    $currentDefaultPayload = ConvertFrom-JsonText -Text $currentDefault.Stdout -Description "get-policy-version"
    $currentDocumentJson = ConvertTo-CompressedJson -Value $currentDefaultPayload.PolicyVersion.Document
    $newDocumentJson = ConvertTo-CompressedJson -Value $PolicyDocument
    if ($currentDocumentJson -eq $newDocumentJson) {
        Write-Host "Policy $ExistingPolicyArn already has the generated document as default version $defaultVersionId."
        return $ExistingPolicyArn
    }

    if (@($versionList).Count -ge 5) {
        $oldestNonDefault = @($versionList | Where-Object { -not $_.IsDefaultVersion } | Sort-Object { [datetime]$_.CreateDate } | Select-Object -First 1)
        if (@($oldestNonDefault).Count -eq 0) {
            throw "Policy $ExistingPolicyArn has 5 versions but no non-default version to delete."
        }
        $versionId = [string]$oldestNonDefault[0].VersionId
        Invoke-AwsCli -Arguments @("iam", "delete-policy-version", "--policy-arn", $ExistingPolicyArn, "--version-id", $versionId, "--output", "json") -OutputPath (Join-Path $Directory "09-delete-oldest-non-default-policy-version.json") | Out-Null
    }

    Invoke-AwsCli -Arguments @("iam", "create-policy-version", "--policy-arn", $ExistingPolicyArn, "--policy-document", $policyDocumentUri, "--set-as-default", "--output", "json") -OutputPath (Join-Path $Directory "10-create-policy-version.json") | Out-Null
    return $ExistingPolicyArn
}

function Confirm-PolicyAttached {
    param(
        [string]$TargetUserName,
        [string]$PolicyArn,
        [string]$Directory
    )

    $attached = Invoke-AwsCli -Arguments @("iam", "list-attached-user-policies", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "11-after-attach-list-attached-user-policies.json")
    $payload = ConvertFrom-JsonText -Text $attached.Stdout -Description "after-attach list-attached-user-policies"
    $arns = ConvertTo-StringArray -Value (@($payload.AttachedPolicies) | ForEach-Object { $_.PolicyArn })
    if ($arns -notcontains $PolicyArn) {
        throw "Managed policy $PolicyArn was not visible on user $TargetUserName after attach; refusing to remove old direct policies."
    }
}

function Assert-AttachedPolicyQuotaAllowsOrderedMigration {
    param(
        [string[]]$CurrentAttachedPolicyArns,
        [string]$TargetPolicyArn,
        [string]$TargetPolicyName
    )

    if ([string]::IsNullOrWhiteSpace($TargetPolicyArn)) {
        return
    }
    if ($CurrentAttachedPolicyArns -contains $TargetPolicyArn) {
        return
    }
    $currentAttachedCount = Get-StringArrayCount -Value $CurrentAttachedPolicyArns
    if ($currentAttachedCount -lt 10) {
        return
    }

    $details = @(
        "Cannot complete the requested safe ordering because the user already has $currentAttachedCount directly attached managed policies.",
        "AWS IAM rejects attach-user-policy after the PoliciesPerUser quota of 10 is reached.",
        "The required ordering says $TargetPolicyName must be attached before old direct user policies are removed.",
        "No old directly attached managed policy was detached by this script."
    )
    throw ($details -join " ")
}

function Assert-DirectPermissionRemovalIsSafe {
    param(
        [string]$TargetUserName,
        [string]$CallerArn,
        [string[]]$CurrentAttachedPolicyArns,
        [string]$KeepPolicyArn,
        [string[]]$GroupNames
    )

    $currentAttachedPolicyArnsNormalized = @(ConvertTo-StringArray -Value $CurrentAttachedPolicyArns)
    $policiesToDetach = @($currentAttachedPolicyArnsNormalized | Where-Object { $_ -ne $KeepPolicyArn })
    if ($policiesToDetach.Count -eq 0) {
        return
    }

    $expectedCallerArn = "arn:aws:iam::*:user/$TargetUserName"
    $callerIsTargetUser = $CallerArn -like $expectedCallerArn
    if (-not $callerIsTargetUser) {
        return
    }

    if ((Get-StringArrayCount -Value $GroupNames) -gt 0) {
        return
    }

    $details = @(
        "Refusing to remove old direct user policies because the active AWS caller is the target user ($CallerArn).",
        "The target user has no group memberships in the saved inventory.",
        "After direct user IAM permissions are removed, this same caller may lose permission before final cleanup and verification complete.",
        "Run the script from a separate administrator principal, or leave the old direct policies in place until an administrator can remove them."
    )
    throw ($details -join " ")
}

function Remove-OldDirectUserPermissions {
    param(
        [string]$TargetUserName,
        [string]$KeepPolicyArn,
        [string]$Directory
    )

    $inline = Invoke-AwsCli -Arguments @("iam", "list-user-policies", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "12-before-removal-list-user-policies.json")
    $inlineNames = ConvertTo-StringArray -Value (ConvertFrom-JsonText -Text $inline.Stdout -Description "before-removal list-user-policies").PolicyNames
    foreach ($inlineName in $inlineNames) {
        $safeName = ConvertTo-SafeFileName -Value $inlineName
        Invoke-AwsCli -Arguments @("iam", "delete-user-policy", "--user-name", $TargetUserName, "--policy-name", $inlineName, "--output", "json") -OutputPath (Join-Path $Directory "13-delete-user-policy-$safeName.json") | Out-Null
    }

    $attached = Invoke-AwsCli -Arguments @("iam", "list-attached-user-policies", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "14-before-removal-list-attached-user-policies.json")
    $attachedArns = ConvertTo-StringArray -Value (@((ConvertFrom-JsonText -Text $attached.Stdout -Description "before-removal list-attached-user-policies").AttachedPolicies) | ForEach-Object { $_.PolicyArn })
    foreach ($attachedArn in $attachedArns) {
        if ($attachedArn -eq $KeepPolicyArn) {
            continue
        }
        $safeArn = ConvertTo-SafeFileName -Value $attachedArn
        Invoke-AwsCli -Arguments @("iam", "detach-user-policy", "--user-name", $TargetUserName, "--policy-arn", $attachedArn, "--output", "json") -OutputPath (Join-Path $Directory "15-detach-user-policy-$safeArn.json") | Out-Null
    }
}

function Get-FinalUserState {
    param(
        [string]$TargetUserName,
        [string]$Directory
    )

    $inline = Invoke-AwsCli -Arguments @("iam", "list-user-policies", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "16-final-list-user-policies.json")
    $attached = Invoke-AwsCli -Arguments @("iam", "list-attached-user-policies", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "17-final-list-attached-user-policies.json")
    $groups = Invoke-AwsCli -Arguments @("iam", "list-groups-for-user", "--user-name", $TargetUserName, "--output", "json") -OutputPath (Join-Path $Directory "18-final-list-groups-for-user.json")

    $inlinePayload = ConvertFrom-JsonText -Text $inline.Stdout -Description "final list-user-policies"
    $attachedPayload = ConvertFrom-JsonText -Text $attached.Stdout -Description "final list-attached-user-policies"
    $groupPayload = ConvertFrom-JsonText -Text $groups.Stdout -Description "final list-groups-for-user"

    return [pscustomobject]@{
        InlinePolicyNames = ConvertTo-StringArray -Value $inlinePayload.PolicyNames
        AttachedPolicyArns = ConvertTo-StringArray -Value (@($attachedPayload.AttachedPolicies) | ForEach-Object { $_.PolicyArn })
        GroupNames = ConvertTo-StringArray -Value (@($groupPayload.Groups) | ForEach-Object { $_.GroupName })
    }
}

function Write-Summary {
    param(
        [string]$PolicyArn,
        [string[]]$InlinePolicyNames,
        [string[]]$AttachedPolicyArns,
        [string[]]$GroupNames,
        [string]$Directory,
        [bool]$IsDryRun
    )

    if ($IsDryRun) {
        Write-Host ""
        Write-Host "DRY RUN complete. No AWS CLI command was executed and IAM was not mutated."
    }
    else {
        Write-Host ""
        Write-Host "IAM permission migration complete."
    }
    Write-Host "Policy ARN: $PolicyArn"
    Write-Host "Remaining inline policy names for user ${UserName}: $(Format-StringArrayOrNone -Value $InlinePolicyNames)"
    Write-Host "Remaining directly attached policy ARNs for user ${UserName}: $(Format-StringArrayOrNone -Value $AttachedPolicyArns)"
    Write-Host "Group memberships for user ${UserName}: $(Format-StringArrayOrNone -Value $GroupNames)"
    Write-Host "Backup directory: $Directory"
}

function Write-DryRunPlan {
    param(
        [string]$Directory,
        [string]$PolicyDocumentPath,
        [string]$PlannedPolicyArn
    )

    $policyDocumentUri = "file://$($PolicyDocumentPath.Replace('\', '/'))"
    $commands = @(
        "# Read-only inventory commands that real execution saves before IAM mutation.",
        (Format-AwsCommand -Arguments @("iam", "list-user-policies", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "get-user-policy", "--user-name", $UserName, "--policy-name", "<each-inline-policy-name-from-list-user-policies>", "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-attached-user-policies", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-groups-for-user", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("sts", "get-caller-identity", "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-policies", "--scope", "Local", "--output", "json")),
        "",
        "# Mutation commands. Real execution runs one create/update branch, attaches first, then removes old direct user permissions.",
        (Format-AwsCommand -Arguments @("iam", "create-policy", "--policy-name", $PolicyName, "--policy-document", $policyDocumentUri, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-policy-versions", "--policy-arn", $PlannedPolicyArn, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "delete-policy-version", "--policy-arn", $PlannedPolicyArn, "--version-id", "<oldest-non-default-version-if-policy-already-has-five-versions>", "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "create-policy-version", "--policy-arn", $PlannedPolicyArn, "--policy-document", $policyDocumentUri, "--set-as-default", "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "attach-user-policy", "--user-name", $UserName, "--policy-arn", $PlannedPolicyArn, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-attached-user-policies", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-user-policies", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "delete-user-policy", "--user-name", $UserName, "--policy-name", "<each-inline-policy-name-after-attach>", "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-attached-user-policies", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "detach-user-policy", "--user-name", $UserName, "--policy-arn", "<each-direct-policy-arn-except-$PolicyName>", "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-user-policies", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-attached-user-policies", "--user-name", $UserName, "--output", "json")),
        (Format-AwsCommand -Arguments @("iam", "list-groups-for-user", "--user-name", $UserName, "--output", "json"))
    )

    $planPath = Join-Path $Directory "planned-aws-cli-commands.txt"
    Write-TextFile -Path $planPath -Text (($commands -join [Environment]::NewLine) + [Environment]::NewLine)
    Write-Host "Dry-run AWS CLI command plan:"
    foreach ($command in $commands) {
        if ($command) {
            Write-Host $command
        }
    }
    Write-Host "Plan written to $planPath"
}

if ($DryRun -and $ExecuteIamMutation) {
    throw "Use either -DryRun or -ExecuteIamMutation, not both."
}
if (-not $DryRun -and -not $ExecuteIamMutation) {
    throw "Refusing IAM mutation without -ExecuteIamMutation. Use -DryRun to generate the policy and command plan without AWS calls."
}
if ([string]::IsNullOrWhiteSpace($UserName)) {
    throw "UserName must not be empty."
}
if ([string]::IsNullOrWhiteSpace($PolicyName)) {
    throw "PolicyName must not be empty."
}
if (-not $DryRun -and -not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI executable 'aws' was not found on PATH."
}

$backupDirectory = New-RunBackupDirectory -Root $BackupRoot
$policyPath = Join-Path $backupDirectory "orket-northstar-work-policy.json"
$policyDocument = New-OrketNorthstarPolicyDocument -BucketNamePrefix $BucketPrefix
$policySize = Save-PolicyDocument -PolicyDocument $policyDocument -OutputPath $policyPath
Write-Host "Generated policy JSON: $policyPath"
Write-Host "Generated policy non-whitespace character count: $policySize"

if ($DryRun) {
    $plannedArn = "arn:aws:iam::<account-id>:policy/$PolicyName"
    Write-DryRunPlan -Directory $backupDirectory -PolicyDocumentPath $policyPath -PlannedPolicyArn $plannedArn
    Write-Summary -PolicyArn $plannedArn -InlinePolicyNames @("<not-queried-in-dry-run>") -AttachedPolicyArns @("<not-queried-in-dry-run>") -GroupNames @("<not-queried-in-dry-run>") -Directory $backupDirectory -IsDryRun $true
    exit 0
}

$inventory = Save-CurrentInventory -TargetUserName $UserName -Directory $backupDirectory
$existingPolicyArn = Find-CustomerManagedPolicyArn -TargetPolicyName $PolicyName -Directory $backupDirectory
Assert-AttachedPolicyQuotaAllowsOrderedMigration -CurrentAttachedPolicyArns $inventory.AttachedPolicyArns -TargetPolicyArn $existingPolicyArn -TargetPolicyName $PolicyName
$policyArn = Ensure-CustomerManagedPolicy -ExistingPolicyArn $existingPolicyArn -TargetPolicyName $PolicyName -PolicyDocument $policyDocument -PolicyDocumentPath $policyPath -Directory $backupDirectory

Invoke-AwsCli -Arguments @("iam", "attach-user-policy", "--user-name", $UserName, "--policy-arn", $policyArn, "--output", "json") -OutputPath (Join-Path $backupDirectory "11-attach-user-policy.json") | Out-Null
Confirm-PolicyAttached -TargetUserName $UserName -PolicyArn $policyArn -Directory $backupDirectory
Assert-DirectPermissionRemovalIsSafe -TargetUserName $UserName -CallerArn $inventory.CallerArn -CurrentAttachedPolicyArns $inventory.AttachedPolicyArns -KeepPolicyArn $policyArn -GroupNames $inventory.GroupNames
Remove-OldDirectUserPermissions -TargetUserName $UserName -KeepPolicyArn $policyArn -Directory $backupDirectory
$finalState = Get-FinalUserState -TargetUserName $UserName -Directory $backupDirectory
Write-Summary -PolicyArn $policyArn -InlinePolicyNames $finalState.InlinePolicyNames -AttachedPolicyArns $finalState.AttachedPolicyArns -GroupNames $finalState.GroupNames -Directory $backupDirectory -IsDryRun $false
