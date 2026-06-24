"use client";
import {
  unstableSetRender
} from "./chunk-ICB6JKB4.js";
import {
  require_client
} from "./chunk-YEXXCPJU.js";
import "./chunk-MXRSIHXN.js";
import "./chunk-DBN6MBR3.js";
import "./chunk-HIWPW72E.js";
import {
  __toESM
} from "./chunk-G3PMV62Z.js";

// node_modules/@ant-design/v5-patch-for-react-19/es/index.js
var import_client = __toESM(require_client());
unstableSetRender(function(node, container) {
  container._reactRoot || (container._reactRoot = (0, import_client.createRoot)(container));
  var root = container._reactRoot;
  root.render(node);
  return function() {
    return new Promise(function(resolve) {
      setTimeout(function() {
        root.unmount();
        resolve();
      }, 0);
    });
  };
});
//# sourceMappingURL=@ant-design_v5-patch-for-react-19.js.map
