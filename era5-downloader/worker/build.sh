AWS_ACCOUNT_ID=`aws sts get-caller-identity --query Account --output text`
ECR="dev-mgd-ict-platform-horta-wf-worker-image"
REGION="eu-west-1"

echo "This image will be builded and pushed in $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR"
echo "Press 'y' to proceed, any other key to cancel."
read A
if [ $A = "y" ]; then
    echo "Loggin into ECR..."
    aws ecr get-login --no-include-email >> err.txt
    `aws ecr get-login --no-include-email` >> err.txt
    rm err.txt
    echo "Building image \"$ECR\" ..."
    docker build -t $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR .
    echo "Pushing image..."
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR

    $(aws ecr get-login --no-include-email --region $REGION)

else
    echo "Canceled."
fi