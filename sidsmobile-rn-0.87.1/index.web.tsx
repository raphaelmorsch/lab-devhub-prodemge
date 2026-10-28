import {AppRegistry} from 'react-native';
import App from './App';
import {name as appName} from './app.json';

const rootTag = document.getElementById('root');

if (rootTag == null) {
  throw new Error('Elemento #root não encontrado');
}

AppRegistry.registerComponent(appName, () => App);
AppRegistry.runApplication(appName, {rootTag});
