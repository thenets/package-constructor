FROM my.local/base-image

RUN echo "Hello World" > /hello.txt

CMD ["cat", "/hello.txt"]
