import React from 'react';
import './App.css';

import { Intent, Toaster, Spinner, Button, HTMLTable, Icon, Tooltip, Position, Popover, ProgressBar, Card, H4, Dialog, Classes, AnchorButton, FormGroup, InputGroup, Callout, UL } from "@blueprintjs/core";
import { IconNames } from "@blueprintjs/icons";
import { show } from '@blueprintjs/core/lib/esm/components/context-menu/contextMenu';
import { reject } from 'q';

const toaster = Toaster.create();
export const showError = (error: JSX.Element | string) => {
  toaster.show({
    action: {
      text: <strong>{error}</strong>,
      intent: Intent.DANGER,
      icon: IconNames.WARNING_SIGN
    },
    message: "Hiba",
    intent: Intent.DANGER
  });
}

export const showSuccess = (message: JSX.Element | string) => {
  toaster.show({
    action: {
      text: message,
      intent: Intent.SUCCESS,
      icon: IconNames.TICK
    },
    message: "Sikeres művelet",
    intent: Intent.SUCCESS
  });
}

enum WifiAuthMode {
  OPEN = 0,
  WEP = 1,
  WPA_PSK = 2,
  WPA2_PSK = 3,
  WPA_WPA2_PSK = 4
}
const WIFI_AUTH_MODE_NAMES: string[] = ["Nyílt", "WEP", "WPA PSK", "WPA2 PSK", "WPA/WPA2 PSK"];

enum WifiStatus {
  IDLE = 0,
  CONNECTING = 1,
  WRONG_PASSWORD = 2,
  NO_AP_FOUND = 3,
  CONNECT_FAIL = 4,
  GOT_IP = 5
}
const WIFI_STATUS_NAMES: string[] = [
  "Tétlen", "Csatlakozás", "Rossz jelszó", "Access Point nem található",
  "Sikertelen csatlakozás", "IP cím megszerezve"
];



export interface IWifiNetworkInfo {
  ssid: string;
  bssid: string;
  channel: number;
  rssi: number;
  authmode: WifiAuthMode,
  hidden: boolean;
}

export interface IWifiNetworkParams {
  ssid: string;
  password: string;
  ip?: string;
  last_ifconfig?: string[];
}

export interface IWifiIfconfig {
  ip: string;
  netmask: string;
  gw: string;
  dns: string;
}

const tupleToIfconfig = (value: string[]): IWifiIfconfig => {
  return { ip: value[0], netmask: value[1], gw: value[2], dns: value[3] }
}

export type IAllNetworkParams = { [ssid: string]: IWifiNetworkParams };

export class API {
  private server: string;

  public constructor(server: string) {
    this.server = server;
  }

  public call = async (params: any): Promise<any> => {
    const url = this.server + "api/" + new Buffer(JSON.stringify(params)).toString('hex');
    return fetch(url)
      .then((response) => { return response.json(); })
      .catch((error) => { showError(""+error); return Promise.reject(error); });
  }

  public scan_wifi_networks = async (): Promise<IWifiNetworkInfo[]> => {
    try {
      const items: any[][] = await this.call({ op: "scan_wifi" });
      if (!items) {
        reject("Nem sikerült listázni a hálózatokat, próbálja újra.");
      }
      let result: IWifiNetworkInfo[] = [];
      items.forEach((item: any[]) => {
        result.push({
          ssid: item[0],
          bssid: item[1],
          channel: item[2],
          rssi: item[3],
          authmode: item[4],
          hidden: item[5] ? true : false,
        })
      });
      // Sort by signal strength
      result.sort((a: IWifiNetworkInfo, b: IWifiNetworkInfo) => b.rssi - a.rssi);
      return Promise.resolve(result);
    } catch (error) {
      return Promise.reject(error);
    }
  }

  public get_wifi_params = async (): Promise<IAllNetworkParams> => {
    try {
      return (await this.call({ op: "get_wifi_params" })) as IAllNetworkParams;
    } catch (error) {
      return Promise.reject(error);
    }
  }

  public set_wifi_param = async (params: IWifiNetworkParams) => {
    try {
      return (await this.call({ op: "set_wifi_param", params }));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  public connect_configured_wifi = async (ssid: string) => {
    try {
      return (await this.call({ op: "connect_configured_wifi", ssid }));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  public ifconfig = async (): Promise<string[] | null> => {
    try {
      return await this.call({ op: "ifconfig" });
    } catch (error) {
      return Promise.reject(error);
    }
  }

  public ap_status = async (): Promise<number> => {
    try {
      return await this.call({ op: "ap_status" });
    } catch (error) {
      return Promise.reject(error);
    }
  }

  public reset = async () => {
    try {
      return (await this.call({ op: "reset" }));
    } catch (error) {
      return Promise.reject(error);
    }
  }  

}



const SERVER = '/';
const api = new API(SERVER);

interface IAppProps {

}

interface IAppState {
  loading: boolean;
  configured : boolean;
  connecting: boolean;
  try_status: string | null;
  try_elapsed: number | null;
  networks: IWifiNetworkInfo[];
  selectedNetwork: number | null;
  params: IAllNetworkParams;
}

class App extends React.Component<IAppProps, IAppState> {
  constructor(props: IAppProps) {
    super(props);
    this.state = {
      loading: true,
      configured: false,
      try_status: null, try_elapsed: null, connecting: false,
      networks: [], selectedNetwork: null, params: {}
    };
  }

  componentDidMount() {
    this.fullReload();
  }

  private scanWifi = async () => {
    this.setState({ loading: true });
    try {
      const networks = await api.scan_wifi_networks();
      this.setState({ loading: false, networks });
    } catch (error) {
      console.log(error);
      showError(""+error);
    }
  }

  private reset = async () => {
    this.setState({loading: true});
    try {
      await api.reset();
    } catch (error) {
      console.log(error);
      showError(""+error);
    }
  }

  private fullReload = async () => {
    this.setState({ loading: true });
    try {
      const networks = await api.scan_wifi_networks();
      const params = await api.get_wifi_params();
      this.setState({ loading: false, networks, params });
    } catch (error) {
      console.log(error);
      showError(""+error);
    }
  }

  private rssiSignalStrength = (rssi: number): number => {
    return (100 + rssi) / 100.0;
  }

  private rssiIntent = (rssi: number): Intent => {
    // See https://www.metageek.com/training/resources/wifi-signal-strength-basics.html
    if (rssi >= -30) {
      return Intent.SUCCESS;
    } else if (rssi >= -67) {
      return Intent.PRIMARY;
    } else if (rssi > -70) {
      return Intent.WARNING
    } else {
      return Intent.DANGER;
    }
  }

  private closeDialog = () => {
    this.setState({ selectedNetwork: null, connecting: false, try_status: null });
  }

  private networkEditor = () => {
    if (this.state.selectedNetwork == null) {
      return null;
    }
    const network = this.getSelectedNetwork()!;
    const params = this.getSelectedParams()!;
    return <>
      <FormGroup
        label="Hálózat neve (SSID)"
        labelFor="ssid-input"
        labelInfo="(kötelező)"
      >
        <InputGroup
          id="ssid-input"
          value={network.ssid}
          readOnly={true}
          leftIcon={IconNames.TAG}
        />
        <ProgressBar
          intent={this.rssiIntent(network.rssi)}
          value={this.rssiSignalStrength(network.rssi)}
          stripes={false}
        />
      </FormGroup>
      <FormGroup
        helperText="Írja be a hálózat jelszavát"
        label="Jelszó"
        labelFor="password-input"
        labelInfo="(kötelező)"
      >
        <InputGroup
          id="password-input"
          placeholder="Írja be a jelszót"
          type="password"
          leftIcon={IconNames.KEY}
          disabled={network.authmode == WifiAuthMode.OPEN}
          value={params.password}
          onChange={(event: any) => this.updateSelectedParams({ password: event.target.value })}
        />
      </FormGroup>
    </>
  }

  private selectNetwork = (index: number) => {
    this.setState({ selectedNetwork: index });
  }

  private getSelectedNetwork = (): IWifiNetworkInfo | null => {
    if (this.state.selectedNetwork == null) {
      return null;
    } else {
      return this.state.networks[this.state.selectedNetwork];
    }
  }

  private getSelectedParams = (): IWifiNetworkParams | null => {
    const network = this.getSelectedNetwork();
    if (network) {
      const params = this.state.params[network.ssid];
      return params || { ssid: network.ssid, password: "" };
    } else {
      return null;
    }
  }

  private updateSelectedParams = (updates: Partial<IWifiNetworkParams>) => {
    const selectedParams: IWifiNetworkParams = { ...this.getSelectedParams()!, ...updates };
    const params = { ...this.state.params, [selectedParams.ssid]: selectedParams }
    this.setState({ params });
  }


  private testCurrentNetwork = async () => {
    try {
      this.setState({ try_status: "Új konfiguráció küldése", connecting: true });
      const params = this.getSelectedParams()!;
      await api.set_wifi_param(params);
      this.setState({ try_status: "Csatlakozás indítása" });
      await api.connect_configured_wifi(params.ssid);
      this.setState({ try_status: "Várakozás a kapcsolódásra...", try_elapsed: 0 });
      setTimeout(this.monitorCurrentNetwork, 500);
    } catch (error) {
      showError(""+error);
      this.setState({ try_status: null, connecting: false });
    }
  }

  private monitorCurrentNetwork = async () => {
    // Ha a bezár gombot nyomta meg, akkor itt meg is szakad a státusz lekérdezés.
    if (this.state.selectedNetwork==null) {
      return;
    }
    try {
      this.setState({ try_elapsed: (this.state.try_elapsed || 0) + 0.5 });
      const status: number = await api.ap_status();
      const statusName: string = WIFI_STATUS_NAMES[status];
      this.setState({ try_status: statusName,
        connecting:  status == WifiStatus.CONNECTING});

      if (status == WifiStatus.CONNECTING) {
        setTimeout(this.monitorCurrentNetwork, 500);
      } else if (status == WifiStatus.IDLE) {
        return;
      } else if (status == WifiStatus.GOT_IP) {
        const ifconfig: string[] | null = await api.ifconfig();
        if (ifconfig) {
          this.updateSelectedParams({ last_ifconfig: ifconfig });
          this.setState({selectedNetwork: null, configured: true});
          showSuccess(
            <>
              <H4>Sikeres kapcsolódás!</H4>
              <UL>
                <li>IP cím: {ifconfig[0]}</li>
                <li>Alhálózati maszk: {ifconfig[1]}</li>
                <li>Átjáró: {ifconfig[2]}</li>
                <li>DNS: {ifconfig[3]}</li>
              </UL>
            </>
          );
        } else {
          showError(
            <>
              <H4>Sikertelen kapcsolódás!</H4>
              <p>Belső hiba - az ezköz sikeres kapcsolódást jelentett,
                de nem kapott IP címet.
              </p>
            </>
          )
        }
      } else {
        showError(
          <>
            <H4>Sikertelen kapcsolódás!</H4>
            <p>{statusName}</p>
          </>
        )
      }
    } catch (error) {
      showError(""+error);
      this.setState({ try_status: null, connecting: false });
    }
  }

  private lastIfconfig = (network: IWifiNetworkInfo) => {
    const params = this.state.params[network.ssid];
    if (params && params.last_ifconfig) {
      const ifconfig = params.last_ifconfig;
      return <UL>
        <li>Cím: {ifconfig[0]}</li>
        <li>Maszk: {ifconfig[1]}</li>
        <li>Átjáró: {ifconfig[2]}</li>
        <li>DNS: {ifconfig[3]}</li>
      </UL>
    }
    return null;
  }

  render() {
    return (
      <div className="page">
        <H4>Wifi beállítása</H4>
        <div className={Classes.RUNNING_TEXT} key="header-text">
          Az eszköz megfelelő működéséhez kapcsolódnia kell egy olyan Wi-Fi hálózatra, amin keresztül
          elérhető az internet. Válasszon legalább egyet az alábbi lehetőségek közül.
        </div>
        <Dialog
          isOpen={this.state.selectedNetwork !== null}
          icon={IconNames.SETTINGS}
          title="Kapcsolódási paraméterek megadása"
          onClose={this.closeDialog}
        >
          <div className={Classes.DIALOG_BODY}>
            {this.networkEditor()}
          </div>
          <div className={Classes.DIALOG_FOOTER}>
            {this.state.try_status ?
              <Callout intent={Intent.PRIMARY}>
                {this.state.try_status}...
                  {this.state.try_elapsed === null ? null : ` (${this.state.try_elapsed} s)`}
              </Callout>
              : null}
            <div className={Classes.DIALOG_FOOTER_ACTIONS}>
              <Tooltip content="Bezárás a módosítások mentése nélkül">
                <Button icon={IconNames.CROSS} onClick={this.closeDialog}>Bezár</Button>
              </Tooltip>
              {/* Mobilon nem jó a tooltip...              
              <Tooltip content="Megpróbál csatlakozni a hálózathoz a megadott paraméterekkel">*/}
                <Button
                  intent={Intent.PRIMARY}
                  onClick={this.testCurrentNetwork}
                  loading={this.state.connecting}
                >
                  Beállítások kipróbálása...
                </Button>
                {/*</Tooltip>*/}
            </div>
          </div>
        </Dialog>
        <Button onClick={() => this.scanWifi()} disabled={this.state.loading}
          icon={IconNames.SEARCH}
        >
          {this.state.loading ? <Spinner /> : <span>Hálózat lista újratöltése</span>}
        </Button>
        <Button onClick={() => this.reset()} disabled={this.state.loading || !this.state.configured}
          icon={IconNames.POWER}
        >
            <span>Befejez <br />(Újraindítás)</span>
        </Button>
        {!this.state.loading && this.state.networks ?
          <HTMLTable interactive={true} striped={true}>
            <thead>
              <tr>
                <th>
                  Hálózat neve<br/>
                  Utolsó konfiguráció
                </th>
                <th className="center">Jelerősség<br/>Csatorna</th>
              </tr>
            </thead>
            <tbody>
              {this.state.networks.map((network: IWifiNetworkInfo, index: number) =>
                <tr key={network.ssid + " " + new Buffer(network.bssid).toString('hex')} onClick={() => this.selectNetwork(index)}
                >
                  <td>
                    <Tooltip
                      key="tooltip-bssid"
                      content={"BSSID: " + new Buffer(network.bssid).toString('hex')}
                      position={Position.RIGHT}>
                      <strong>{network.ssid}</strong>
                    </Tooltip>
                    <br/>
                    {this.lastIfconfig(network)}
                  </td>
                  <td className="center">
                    <ProgressBar
                      intent={this.rssiIntent(network.rssi)}
                      value={this.rssiSignalStrength(network.rssi)}
                      stripes={false}
                    />
                    {network.rssi} dB, Ch={network.channel}
                    &nbsp;
                    <Tooltip
                      content={WIFI_AUTH_MODE_NAMES[network.authmode]}
                      position={Position.RIGHT}>
                      <Icon
                        icon={network.authmode == WifiAuthMode.OPEN ? IconNames.UNLOCK : IconNames.LOCK}
                        intent={
                          network.authmode == WifiAuthMode.OPEN ? Intent.DANGER
                            : network.authmode == WifiAuthMode.WPA2_PSK ? Intent.SUCCESS
                              : Intent.WARNING
                        }
                      />
                    </Tooltip>
                    &nbsp;
                    <Tooltip
                      content={network.hidden ? "Rejtett" : "Látható"}
                      position={Position.RIGHT}>
                      <Icon
                        intent={network.hidden ? Intent.WARNING : Intent.PRIMARY}
                        icon={network.hidden ? IconNames.EYE_OFF : IconNames.EYE_OPEN}
                      />
                    </Tooltip>
                  </td>
                </tr>
              )}
            </tbody>
          </HTMLTable>
          : null}
      </div>
    );
  }
}

export default App;
