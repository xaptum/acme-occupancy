FROM python:3.8.5-buster

ADD requirements.txt /
RUN pip --use-feature=2020-resolver install -r requirements.txt

ADD dashboard.py /

EXPOSE 8050

ENTRYPOINT [ "python", "/dashboard.py" ]
