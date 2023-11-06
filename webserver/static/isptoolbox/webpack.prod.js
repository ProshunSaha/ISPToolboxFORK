// (c) Meta Platforms, Inc. and affiliates
const { ModuleFilenameHelpers } = require('webpack');
const {merge} = require('webpack-merge');
const common = require('./webpack.common.js');

module.exports = merge(common, {
    mode: 'production',
});