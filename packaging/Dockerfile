FROM python

ENV TZ=Europe/Berlin
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

ADD . /logger

RUN apt update && apt install socat -y

WORKDIR /logger

RUN make clean
RUN make init
ENV PATH="/logger/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

CMD . /logger/.venv/bin/activate && exec python3 examples/read_to_csv.py
