// (c) Meta Platforms, Inc. and affiliates. Copyright
const lambda = require('./index.js');

const runTests = async () => {
    await lambda.handler({}, {}, test_callback);
    return;
}
runTests();
