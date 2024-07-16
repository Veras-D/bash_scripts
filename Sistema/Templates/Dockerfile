FROM 

WORKDIR 

COPY 

RUN 

COPY 


FROM scratch

WORKDIR /app

COPY --from=builder /bin/app .

EXPOSE 8080

ENTRYPOINT ["./app"]
