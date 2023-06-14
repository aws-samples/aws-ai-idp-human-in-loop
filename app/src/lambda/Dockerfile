FROM public.ecr.aws/lambda/python:3.10-x86_64
COPY requirements.txt  .
RUN  pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"
COPY *.py ${LAMBDA_TASK_ROOT}/