# Public-release review

The public repository was created from one reviewed source snapshot without the private
repository's Git history.

## Checks performed

- Searched tracked source and documentation for credentials, bearer tokens, private keys, OAuth
  fields containing real values, personal email addresses and absolute user paths.
- Removed user-specific DEVONthink database names from the public source.
- Limited the public DEVONthink allow-list to the database named `Inbox`.
- Excluded IDE settings, caches, environments, build output, logs and application data.
- Confirmed that test credentials are synthetic fixtures only.
- Verified that the application bundle contains no source documents, generated records, API keys,
  OAuth caches, application settings or runtime logs.
- Added project and third-party licensing notices.

## Residual considerations

- The preview bundle is not notarised.
- Users remain responsible for their OpenAI account, API charges and local application licences.
- The project's safeguards do not replace organisational privacy, security, records-management or
  regulatory assessments.
