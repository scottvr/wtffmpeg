#!/bin/bash

USER="scottvr"
# Get the account creation year
START_YEAR=$(gh api graphql -f query='query($login:String!){user(login:$login){createdAt}}' -F login="$USER" --jq '.data.user.createdAt | .[0:4]')
CURRENT_YEAR=$(date +%Y)

echo "Fetching contributions from $START_YEAR to $CURRENT_YEAR..."

for YEAR in $(seq $START_YEAR $CURRENT_YEAR); do
    echo "  Processing $YEAR..."
    
    # Define time window for the specific year
    FROM="${YEAR}-01-01T00:00:00Z"
    TO="${YEAR}-12-31T23:59:59Z"

    # Query all 4 contribution types
    gh api graphql --paginate -F login="$USER" -F from="$FROM" -F to="$TO" -f query='
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          commitContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
          issueContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
          pullRequestContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
          pullRequestReviewContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
        }
      }
    }' --jq '.data.user.contributionsCollection | .[] | .[] | .repository.nameWithOwner' >> raw_repos.txt
done

# Sort, remove duplicates, and filter out empty lines
sort -u raw_repos.txt > final_repos.txt
echo "Done! Unique repositories saved to final_repos.txt"
echo "Total Unique Repos: $(wc -l < final_repos.txt)"

