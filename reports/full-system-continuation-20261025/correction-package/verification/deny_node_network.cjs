'use strict';
// Test preload inherited by child Node runners. Browser pages also block requests.
const deny = () => { throw Error('NETWORK_DISABLED_CORRECTION_QUALIFICATION'); };
const net = require('node:net');
net.Socket.prototype.connect = deny;
require('node:tls').connect = deny;
require('node:dgram').createSocket = deny;
for (const module of ['node:http', 'node:https']) {
  const api = require(module); api.request = deny; api.get = deny;
}
globalThis.fetch = deny;
