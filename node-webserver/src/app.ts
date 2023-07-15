/**
 * Nodejs Server used for high-throughput websocket connections
 * 
 * Django-Channels was not working for high throughput, low latency operations
 */

import * as socketio from 'socket.io';
import django_multiplayer_session_auth_middleware from './middleware/django_auth_middleware';
import { initAutoMergeMap, loadAutoMergeMap, deleteAutoMergeMap, updateAutoMergeMap} from './mapbox-automerge/mapbox-automerge';
const socketIOPort = 8080;
const options = {
    cors: {
        origin: "http://localhost:8000",
        methods: ["GET", "POST"]
    },
    path: '/live'
};
const io = require('socket.io')(options);

// Add the Auth Middleware to add user info to the context
io.use(django_multiplayer_session_auth_middleware);

io.of("/").adapter.on("create-room", async (room: string) => {
    await initAutoMergeMap(room);
});

io.of("/").adapter.on("delete-room", async (room: string) => {
    // TODO achong: When room is deleted we should write to DB
    await deleteAutoMergeMap(room);
});

// Callback for new connections
io.on('connection', async(socket: socketio.Socket) => {
    // Help Typescript
    if(socket.handshake.query.session) {
        console.log(`user: ${socket.handshake.query.user}, joined: ${socket.handshake.query.session}`);
        socket.join(socket.handshake.query.session);

        // Notify Session that we have joined
        io.in(socket.handshake.query.session).emit(
            'multiplayer-msg',
            {
                type: 'userjoin',
                uid: socket.handshake.query.user,
                name: socket.handshake.query.name
            }
        );

        // Initialize Initial AutoMerge
        socket.emit('multiplayer-msg', {
            type: 'initautomergemap',
            map: await loadAutoMergeMap(socket.handshake.query.session as string),
        });

        const welcome_new_user =  (room: string, id: string) => {
            io.to(id).emit('multiplayer-msg',
            {
                type: 'userjoin',
                uid: socket.handshake.query.user,
                name: socket.handshake.query.name
            });
        };

        io.of("/").adapter.on("join-room", welcome_new_user);

        socket.on('multiplayer-msg', async (msg: any) => {
            if(socket.handshake.query.session){
                socket.broadcast.to(socket.handshake.query.session).emit(
                    'multiplayer-msg',
                    {
                        ...msg,
                        uid: socket.handshake.query.user,
                    }
                );
            }
            if(msg.type === 'isp.drawedit') {
                await updateAutoMergeMap(socket.handshake.query.session as string, msg.edit);
            }
        });

        // Add disconnection Callback
        socket.on('disconnect', function() {
            console.log(`user: ${socket.handshake.query.user}, left: ${socket.handshake.query.session}`);
            io.of("/").adapter.off("join-room", welcome_new_user);
            // Notify Session that user has left
            io.to(socket.handshake.query.session).emit(
                'multiplayer-msg',
                {
                    type: 'userleave',
                    uid: socket.handshake.query.user,
                }
            );
        });
    }


});

console.log(`Listening for connections on port: https://0.0.0.0:${socketIOPort}`);
io.listen(socketIOPort);
