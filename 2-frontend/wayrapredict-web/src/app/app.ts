import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AvisoService } from './service/aviso.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: `
    <router-outlet/>
    @if (avisoService.aviso(); as a) {
      <div class="toast" [class.toast--error]="a.error" role="status">
        <span class="ok"><svg class="ico" aria-hidden="true"><use [attr.href]="a.error ? '#i-close' : '#i-check'"/></svg></span>
        {{ a.texto }}
      </div>
    }
  `,
})
export class App {
  constructor(public avisoService: AvisoService) {}
}
