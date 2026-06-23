import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Button, Card, Checkbox, Collapse, Empty, Space, Typography } from "antd";

import { showError, showSuccess } from "../Feedback";
import {
  listAgencyGrantedPermissions,
  listPermissionDefinitions,
  updateAgencyGrantedPermissions,
  type PermissionModule,
} from "../../services/permissions";

type AgencyPermissionGrantsPanelProps = {
  agencyId: string;
};

function getAssignableModules(definitions: PermissionModule[]): PermissionModule[] {
  return definitions
    .map((module) => ({
      ...module,
      permissions: module.permissions.filter((permission) => !permission.super_admin_only),
    }))
    .filter((module) => module.permissions.length > 0);
}

function mergePermissionCodes(previous: string[], nextCodes: string[], checked: boolean): string[] {
  if (checked) {
    return Array.from(new Set([...previous, ...nextCodes])).sort();
  }
  return previous.filter((item) => !nextCodes.includes(item));
}

function sanitizePermissionCodes(permissionCodes: string[], allowedCodes: string[]): string[] {
  const allowed = new Set(allowedCodes);
  return permissionCodes.filter((code) => allowed.has(code)).sort();
}

export function AgencyPermissionGrantsPanel({
  agencyId,
}: AgencyPermissionGrantsPanelProps): JSX.Element {
  const [definitions, setDefinitions] = useState<PermissionModule[]>([]);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const assignableModules = useMemo(() => getAssignableModules(definitions), [definitions]);
  const allAssignablePermissionCodes = useMemo(
    () => assignableModules.flatMap((module) => module.permissions.map((permission) => permission.code)),
    [assignableModules],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextDefinitions, nextGranted] = await Promise.all([
        listPermissionDefinitions(),
        listAgencyGrantedPermissions(agencyId),
      ]);
      const nextAssignableModules = getAssignableModules(nextDefinitions);
      const nextAllowedCodes = nextAssignableModules.flatMap((module) =>
        module.permissions.map((permission) => permission.code),
      );
      setDefinitions(nextDefinitions);
      setPermissions(sanitizePermissionCodes(nextGranted.permissions, nextAllowedCodes));
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "加载代理权限池失败");
      setDefinitions([]);
      setPermissions([]);
    } finally {
      setLoading(false);
    }
  }, [agencyId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const nextPermissions = sanitizePermissionCodes(permissions, allAssignablePermissionCodes);
      const result = await updateAgencyGrantedPermissions(agencyId, nextPermissions);
      setPermissions(sanitizePermissionCodes(result.permissions, allAssignablePermissionCodes));
      showSuccess("代理权限池已更新");
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "保存代理权限池失败");
    } finally {
      setSaving(false);
    }
  }, [agencyId, allAssignablePermissionCodes, permissions]);

  return (
    <Card
      title="权限池"
      extra={(
        <Space wrap>
          <Button onClick={() => setPermissions(allAssignablePermissionCodes)}>全选</Button>
          <Button onClick={() => setPermissions([])}>清空</Button>
          <Button type="primary" loading={saving} onClick={() => void handleSave()}>
            保存
          </Button>
        </Space>
      )}
      loading={loading}
      size="small"
    >
      {!loading && assignableModules.length === 0 ? (
        <Empty description="暂无可授予权限" />
      ) : (
        <>
          <Typography.Paragraph type="secondary">
            超管先在这里配置代理可下放的权限池，代理角色只能从这组权限中继续分配。
          </Typography.Paragraph>
          {assignableModules.map((module) => {
            const moduleLabel = module.label || module.module;
            const moduleCodes = module.permissions.map((permission) => permission.code);
            return (
              <Collapse
                key={module.module}
                defaultActiveKey={[module.module]}
                items={[
                  {
                    key: module.module,
                    label: <Typography.Text strong>{moduleLabel}</Typography.Text>,
                    children: (
                      <Space direction="vertical" size={12} style={{ width: "100%" }}>
                        <Space wrap>
                          <Button
                            size="small"
                            onClick={() =>
                              setPermissions((previous) => mergePermissionCodes(previous, moduleCodes, true))
                            }
                          >
                            {`${moduleLabel}全选`}
                          </Button>
                          <Button
                            size="small"
                            onClick={() =>
                              setPermissions((previous) => mergePermissionCodes(previous, moduleCodes, false))
                            }
                          >
                            {`${moduleLabel}清空`}
                          </Button>
                        </Space>
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                            gap: 8,
                          }}
                        >
                          {module.permissions.map((permission) => (
                            <Checkbox
                              key={permission.code}
                              checked={permissions.includes(permission.code)}
                              onChange={(event) => {
                                const checked = event.target.checked;
                                setPermissions((previous) =>
                                  mergePermissionCodes(previous, [permission.code], checked),
                                );
                              }}
                            >
                              {permission.label}
                            </Checkbox>
                          ))}
                        </div>
                      </Space>
                    ),
                  },
                ]}
              />
            );
          })}
        </>
      )}
    </Card>
  );
}
