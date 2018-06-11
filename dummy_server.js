var zerorpc = require("zerorpc");

var server = new zerorpc.Server({
    areYouThere: function(reply) {
        reply(null, "Hello");
    }
});

server.bind("tcp://0.0.0.0:9001");