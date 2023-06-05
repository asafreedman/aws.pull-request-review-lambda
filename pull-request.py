import boto3
import json
"""
Creates pipelines for each pull request and reruns the pipeline in the event 
that the source changes for the PR.

Ideally, when the branch that started the PR is deleted or the pull request is 
set to a closed state so will the pipeline be.

Assumes that the CodeBuild project will already be set up ahead of time.

Needed: 
Service role for the pipeline and build steps
Sufficient permissions to create the pipeline and notification rule for the 
lambda
"""
def lambda_handler(event, context):
    service_role_arn = '***** Service role ARN'
    message = event['Records'][0]['Sns']['Message']
    # In testing this is already an object
    if isinstance(message, str):
        message = json.loads(message)
        
    detail      = message['detail']
    detail_type = message['detailType']
    
    codepipeline_client = boto3.client('codepipeline')

    # Event initiated by creating a pull request
    if detail_type == 'CodeCommit Pull Request State Change':
        status          = detail['pullRequestStatus']
        event           = detail['event']
        # This will come in as something like refs/head/branch
        pr_branch       = detail['sourceReference'].split('/')[-1]
        pr_id           = detail['pullRequestId']
        repo_name       = detail['repositoryNames'][0]
        before_commit   = detail['destinationCommit']
        after_commit    = detail['sourceCommit']
        
        codestar_client = boto3.client('codestar-notifications')
        
        if event == 'pullRequestCreated':
            # You don't need to explicitly start the pipeline on creation
            codepipeline_client.create_pipeline(
                pipeline = {
                    'name': f'***** Pipeline name',
                    'roleArn': service_role_arn,
                    'artifactStore': {
                        'type': 'S3',
                        'location': '***** S3 build storage bucket'
                    },
                    'stages': [{
                        'name': 'Source',
                        'actions': [{
                            'name': 'Source',
                            'actionTypeId': {
                                'category': 'Source',
                                'owner': 'AWS',
                                'provider': 'CodeCommit',
                                'version': '1'
                            },
                            'configuration': {
                                'RepositoryName': '***** Repository',
                                'BranchName': pr_branch,
                                'PollForSourceChanges': 'false'
                            },
                            'outputArtifacts': [
                                {
                                    'name': 'repo'
                                },
                            ],
                            'roleArn': service_role_arn,
                        }]
                    }, {
                        'name': 'Test',
                        'actions': [{
                            'name': 'Test',
                            'actionTypeId': {
                                'category': 'Test',
                                'owner': 'AWS',
                                'provider': 'CodeBuild',
                                'version': '1'
                            },
                            'configuration': {
                                'ProjectName': '***** Project name'
                            },
                            'inputArtifacts': [
                                {
                                    'name': 'repo'
                                },
                            ],
                            'roleArn': service_role_arn,
                        }]
                    }]
                }, 
                # Using these to set context for the future
                tags = [{
                        'key': 'pr_branch'      ,'value': pr_branch
                    }, {
                        'key': 'pr_id'          ,'value': pr_id
                    }, {
                        'key': 'repo_name'      ,'value': repo_name
                    }, {
                        'key': 'before_commit'  ,'value': before_commit
                    }, {
                        'key': 'after_commit'   ,'value': after_commit
                }]
            )
            
            codestar_client.create_notification_rule(
                Name          = '***** Name of the notification rule',
                EventTypeIds  = [
                    'codepipeline-pipeline-pipeline-execution-failed',
                    'codepipeline-pipeline-pipeline-execution-canceled',
                    'codepipeline-pipeline-pipeline-execution-started'
                ],
                Resource      = f'***** ARN of the pipeline created above',
                Targets=[
                    {
                        'TargetType': 'SNS',
                        'TargetAddress': '***** ARN of the target topic'
                    }
                ],
                DetailType    = 'BASIC',
                Status        = 'ENABLED'
            )
        elif event == 'pullRequestSourceBranchUpdated':
            # Commits will have changed that mark the PR therefore, the place 
            # where we need to put comments will as well
            codepipeline_client.tag_resource(
                resourceArn = f'***** ARN of the pipeline created above',
                tags = [{
                    'key': 'before',
                    'value': before_commit
                }, {
                    'key': 'after',
                    'value': after_commit
                }]
            )
            
            codepipeline_client.start_pipeline_execution(
                name = '***** Pipeline name - not the ARN'
            )
        elif event == 'pullRequestMergeStatusUpdated' or status == 'Closed':
            # try:
            #     codestar_client.delete_notification_rule(
            #         Arn = 
            #     )
            # except: 
            #     continue
            # Don't need the pipeline anymore
            codepipeline_client.delete_pipeline(
                name = '***** Pipeline name - not the ARN'
            )
    # Event initiated by something happening in the pipeline
    elif detail_type == 'CodePipeline Pipeline Execution State Change':
        state           = detail['state']
        pipeline_name   = detail['pipeline']
        
        pipeline_tags = codepipeline_client.list_tags_for_resource(
            resourceArn = f'***** ARN of the pipeline created above'
        )
        
        tags = { tag['key']:tag['value'] for tag in pipeline_tags['tags'] }
        
        codecommit_client = boto3.client('codecommit')
        
        codecommit_client.post_comment_for_pull_request(
            pullRequestId   = tags['pr_id'],
            repositoryName  = tags['repo_name'],
            beforeCommitId  = tags['before_commit'],
            afterCommitId   = tags['after_commit'],
            content         = f'Pipeline Status: {state}'
        )
