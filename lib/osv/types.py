# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Datastore types."""

from google.cloud import ndb

# pylint: disable=relative-beyond-top-level
from . import bug
from . import vulnerability_pb2


def _check_valid_severity(prop, value):
  """Check valid severity."""
  del prop

  if value not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
    raise ValueError('Invalid severity: ' + value)


class IDCounter(ndb.Model):
  """Counter for ID allocations."""
  # Next ID to allocate.
  next_id = ndb.IntegerProperty()


class AffectedCommit(ndb.Model):
  """AffectedCommit entry."""
  # The main bug ID.
  bug_id = ndb.StringProperty()
  # The commit hash.
  commit = ndb.StringProperty()
  # Confidence in this result.
  confidence = ndb.IntegerProperty()
  # Project for the bug.
  project = ndb.StringProperty()
  # Ecosystem for the affected commit.
  ecosystem = ndb.StringProperty()
  # Whether or not the bug is public.
  public = ndb.BooleanProperty()


class RegressResult(ndb.Model):
  """Regression results."""
  # The commit hash.
  commit = ndb.StringProperty(default='')
  # Vulnerability summary.
  summary = ndb.StringProperty()
  # Vulnerability details.
  details = ndb.StringProperty()
  # Error (if any).
  error = ndb.StringProperty()
  # OSS-Fuzz issue ID.
  issue_id = ndb.StringProperty()
  # Project for the bug.
  project = ndb.StringProperty()
  # Package ecosystem for the project.
  ecosystem = ndb.StringProperty()
  # Repo URL.
  repo_url = ndb.StringProperty()
  # Severity of the bug.
  severity = ndb.StringProperty(validator=_check_valid_severity)
  # Reference URLs.
  reference_urls = ndb.StringProperty(repeated=True)
  # Source timestamp.
  timestamp = ndb.DateTimeProperty()


class FixResult(ndb.Model):
  """Fix results."""
  # The commit hash.
  commit = ndb.StringProperty(default='')
  # Vulnerability summary.
  summary = ndb.StringProperty()
  # Vulnerability details.
  details = ndb.StringProperty()
  # Error (if any).
  error = ndb.StringProperty()
  # OSS-Fuzz issue ID.
  issue_id = ndb.StringProperty()
  # Project for the bug.
  project = ndb.StringProperty()
  # Package ecosystem for the project.
  ecosystem = ndb.StringProperty()
  # Repo URL.
  repo_url = ndb.StringProperty()
  # Severity of the bug.
  severity = ndb.StringProperty(validator=_check_valid_severity)
  # Reference URLs.
  reference_urls = ndb.StringProperty(repeated=True)
  # Source timestamp.
  timestamp = ndb.DateTimeProperty()


class PackageInfo(ndb.Model):
  """Package info."""
  # The latest tag for the package.
  latest_tag = ndb.StringProperty()


class PackageTagInfo(ndb.Model):
  """Project tag information."""
  # The name of the package.
  package = ndb.StringProperty()
  # The ecosystem for the package.
  ecosystem = ndb.StringProperty()
  # The tag.
  tag = ndb.StringProperty()
  # List of public bugs.
  bugs = ndb.StringProperty(repeated=True)
  # List of private bugs.
  bugs_private = ndb.StringProperty(repeated=True)


class CommitRange(ndb.Model):
  """Commit range."""
  # The regressing commit.
  introduced_in = ndb.StringProperty()
  # The fix commit.
  fixed_in = ndb.StringProperty()


class Bug(ndb.Model):
  """Bug entity."""
  # Status of the bug.
  status = ndb.IntegerProperty()
  # Timestamp when Bug was allocated.
  timestamp = ndb.DateTimeProperty()
  # The source identifier.
  source_id = ndb.StringProperty()
  # Repo URL.
  repo_url = ndb.StringProperty()
  # The main fixed commit.
  fixed = ndb.StringProperty()
  # The main regressing commit.
  regressed = ndb.StringProperty()
  # Additional affected commit ranges derived from the main fixed and regressed
  # commits.
  additional_commit_ranges = ndb.StructuredProperty(CommitRange, repeated=True)
  # List of affected tags.
  affected = ndb.StringProperty(repeated=True)
  # List of normalized tags for fuzzy matching.
  affected_fuzzy = ndb.StringProperty(repeated=True)
  # Confidence in the commit range and affected tags.
  confidence = ndb.IntegerProperty()
  # OSS-Fuzz issue ID.
  issue_id = ndb.StringProperty()
  # Project for the bug.
  project = ndb.StringProperty()
  # Package ecosystem for the project.
  ecosystem = ndb.StringProperty()
  # Summary for the bug.
  summary = ndb.StringProperty()
  # Vulnerability details.
  details = ndb.StringProperty()
  # Severity of the bug.
  severity = ndb.StringProperty(validator=_check_valid_severity)
  # Whether or not the bug is public.
  public = ndb.BooleanProperty()
  # Reference URLs.
  reference_urls = ndb.StringProperty(repeated=True)
  # Search indices (auto-populated)
  search_indices = ndb.StringProperty(repeated=True)
  # Whether or not the bug has any affected tags (auto-populated).
  has_affected = ndb.BooleanProperty()
  # Sort key.
  sort_key = ndb.StringProperty()

  def _pre_put_hook(self):
    """Pre-put hook for populating search indices."""
    self.search_indices = []
    if self.project:
      self.search_indices.append(self.project)

    key_parts = self.key.id().split('-')
    self.search_indices.append(self.key.id())
    self.search_indices.extend(key_parts)

    self.has_affected = bool(self.affected)
    self.affected_fuzzy = bug.normalize_tags(self.affected)

    self.sort_key = key_parts[0] + '-' + key_parts[1].zfill(7)

  def to_vulnerability(self):
    """Convert to Vulnerability proto."""

    def _to_commit(commit_hash):
      """Convert a commit hash to a Commit structure."""
      return vulnerability_pb2.Commit(
          repo_type=vulnerability_pb2.Commit.RepoType.GIT,
          repo_url=self.repo_url,
          commit=commit_hash)

    fixed = None
    fix_commit = self.fixed
    if fix_commit:
      fixed = _to_commit(fix_commit)

    affected_range = vulnerability_pb2.AffectedRange(
        introduced_in=_to_commit(self.regressed), fixed_in=fixed)

    package = vulnerability_pb2.Package(
        name=self.project, ecosystem=self.ecosystem)

    affects = vulnerability_pb2.Affects(
        ranges=[affected_range], versions=self.affected)

    if self.severity:
      severity = vulnerability_pb2.Vulnerability.Severity.Value(self.severity)
    else:
      severity = vulnerability_pb2.Vulnerability.Severity.NONE

    details = self.details
    if self.status == bug.BugStatus.INVALID:
      affects = None
      details = 'INVALID'
      severity = vulnerability_pb2.Vulnerability.Severity.NONE

    result = vulnerability_pb2.Vulnerability(
        id=self.key.id(),
        summary=self.summary,
        details=details,
        package=package,
        severity=severity,
        affects=affects,
        reference_urls=self.reference_urls)

    return result


class SourceRepository(ndb.Model):
  """Source repository."""
  # The name of the source.
  name = ndb.StringProperty()
  # The repo URL for the source.
  repo_url = ndb.StringProperty()
  # The username to use for SSH auth.
  repo_username = ndb.StringProperty()
  # The directory in the repo where Vulnerability data is stored.
  directory_path = ndb.StringProperty()
  # Last synced hash.
  last_synced_hash = ndb.StringProperty()
