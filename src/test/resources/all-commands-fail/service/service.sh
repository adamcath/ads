while True; do
    echo "$(date) some output from the service"
    echo "$(date) some errors from the service" 1>&2
    sleep 2
done    
