# aws.pull-request-review-lambda

Something that may be useful in the future.

Needs to have an event that directs the pull request created event to an SNS topic. The lambda that uses this code should use that topic as a trigger.

This will create a new CodePipeline pipeline, using an existing CodeBuild project and run the pipeline. The pipeline will then comment on the PR what the exit status of the pipeline was.
I guess the pipeline could also be an approver for the PR but right now it just comments.

The pipeline should delete once the PR state changes to closed or the PR is merged - technically the same thing.
