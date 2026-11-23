/* Caixa ADXL355 + ESP32-S3 | v0.10 | 05/11/2026
   Unidades: mm. PCB horizontal; shield 18650 V3 em pe na lateral direita.
   Alteracao da v0.9: elimina o cabo USB interno e usa dois fios sob a PCB.
   As envolventes de USB, chave, antena e cabos sao referencias de montagem.
   Para imprimir, escolha parte="base" ou parte="tampa", renderize e exporte.
*/
parte="aberta"; // [base,tampa,aberta,montada,explodida,gabarito_placa,gabarito_shield,calibre_furos,calibre_porcas,arruela,arruela_shield,empurrador_m2,empurrador_m3,cupom_adesivo]
mostrar_cabos=true;
mostrar_reserva=false;
/* [Caixa] */
parede=3; fundo=6; altura=40; raio=6;
interno_y=114;
tampa_t=3; guia_t=1.6; guia_h=3; guia_folga=.30;
/* [PCB e antena] */
placa_x=80; placa_y=60; placa_t=1;
placa_recuo=2; placa_z=14;
projecao_acima=9; projecao_abaixo=6;
antena_projecao=6; folga_antena_parede=20;
antena_largura_ref=26;
placa_origem=[1,antena_projecao+folga_antena_parede];
/* [Shield deitado sobre a borda longa] */
shield_x=100; shield_y=29; shield_t=1.5; shield_recuo=2.5;
shield_altura_total=25;
corredor_lateral=7;
folga_traseira_shield=6;
shield_y_inicio=6;
shield_y_fim=shield_y_inicio+shield_x;
shield_z_borda=8;
shield_x_traseira=placa_origem[0]+placa_x+corredor_lateral+shield_altura_total;
interno_x=shield_x_traseira+folga_traseira_shield;
usb_avanco=6; usb_largura_reservada=17;
/* [Fixacoes] */
furo_m2=2.4; furo_m3=3.4; furo_shield=furo_m3;
porca_m2_AF=4.3; porca_m2_h=1.8;
porca_m3_AF=5.6; porca_m3_h=2.6;
apoio_d=9; pe_d=12; ressalto_t=.4;
arruela_t=.4; arruela_d=5; arruela_shield_d=6;
coluna_tampa_d=11; porca_tampa_z=34.4;
// Torres direitas recuadas em X: deixam o shield e a tomada livres.
colunas_tampa=[[6,6],[76,6],[6,interno_y-6],[76,interno_y-6]];
porca_shield_x=shield_x_traseira+1;
furo_shield_ate_x=shield_x_traseira+5.25;
/* [Rotas e envelopes de servico] */
fio_d=1.4; fio_z=fundo+1;
usb_esp_centro_x=placa_origem[0]+placa_x/2;
usb_esp_face_y=placa_origem[1]+placa_y;
usb_esp_z=21.5; usb_plug_comp=24; usb_plug_larg=20; usb_plug_alt=12;
conector_origem=[59,12.5,6.8]; conector_dim=[16,10,7];
olhal_pos=[64,7];
// Dois fios separados, rente ao fundo. O ponto de solda real deve ser medido.
cabos_shield=[
 [[shield_x_traseira+1.4,52.73,10.6],[shield_x_traseira+1.4,52.73,fio_z],[86.5,52.73,fio_z],[74,46,fio_z],[68.6,34,fio_z],[68.6,18,fio_z],[75.4,16.1,8.5]],
 [[shield_x_traseira+1.4,55.27,10.6],[shield_x_traseira+1.4,55.27,fio_z],[87.3,55.27,fio_z],[75.8,47,fio_z],[71.1,34,fio_z],[71.0,24,fio_z],[71.8,19.5,fio_z],[75.4,19.5,8.5]]
];
cabos_placa=[
 [[59,16.1,8.5],[57.7,19,fio_z],[59.4,29,fio_z],[62,40,fio_z],[68.6,55,fio_z]],
 [[59,19.5,8.5],[61.0,25,fio_z],[62.2,34,fio_z],[64.5,44,fio_z],[71,55,fio_z]]
];
$fn=64; eps=.03;
furos_placa=[for(x=[placa_recuo,placa_x-placa_recuo],y=[placa_recuo,placa_y-placa_recuo]) [x,y]];
furos_shield=[for(x=[shield_recuo,shield_x-shield_recuo],y=[shield_recuo,shield_y-shield_recuo]) [x,y]];
apoios_placa=[for(p=furos_placa) p+placa_origem];
apoios_shield_yz=[for(p=furos_shield) [shield_y_fim-p[0],shield_z_borda+p[1]]];
antena_x=usb_esp_centro_x-antena_largura_ref/2;
antena_z=placa_z+placa_t+8;
assert(placa_origem[1]-antena_projecao==folga_antena_parede);
assert(placa_z-projecao_abaixo-fundo>=2);
assert(fio_z-fio_d/2>fundo && fio_z+fio_d/2<placa_z-projecao_abaixo);
assert(fio_z+fio_d/2<shield_z_borda);
assert(shield_y_fim+usb_avanco<=interno_y-2);
assert(usb_esp_face_y+usb_plug_comp<=interno_y-4);
assert(shield_z_borda+shield_y+2<=altura-1);
assert(shield_x_traseira-shield_t-arruela_t+6<furo_shield_ate_x);
assert(shield_x_traseira-shield_t-arruela_t+6>porca_shield_x+porca_m3_h);
assert(furo_shield_ate_x<interno_x);
echo(versao="0.10",dimensoes_fechada=[interno_x+2*parede,interno_y+2*parede,altura+tampa_t],folga_antena=folga_antena_parede,corredor=corredor_lateral,apoios_shield_yz=apoios_shield_yz);

module centrado() { translate([-interno_x/2,-interno_y/2,0]) children(); }
module retangulo_arredondado(w,h,r) {
    hull() for(x=[r,w-r],y=[r,h-r]) translate([x,y]) circle(r=r);
}
module canal_porcas(p,AF,h,z,direcao="x+",alcance=8) {
    translate([p[0],p[1],z]) {
        rotate([0,0,(direcao=="y-" || direcao=="y+")?30:0]) cylinder(h=h,r=AF/(2*cos(30)),$fn=6);
        if(direcao=="x+") translate([0,-AF/2,0]) cube([alcance,AF,h]);
        if(direcao=="x-") translate([-alcance,-AF/2,0]) cube([alcance,AF,h]);
        if(direcao=="y-") translate([-AF/2,-alcance,0]) cube([AF,alcance,h]);
        if(direcao=="y+") translate([-AF/2,0,0]) cube([AF,alcance,h]);
    }
}
module corpo_apoio(p) {
    translate([p[0],p[1],fundo-eps]) {
        cylinder(h=placa_z-ressalto_t-fundo+eps,d=apoio_d);
        cylinder(h=3+eps,d1=pe_d,d2=apoio_d);
        translate([0,0,placa_z-ressalto_t-fundo]) cylinder(h=ressalto_t+eps,d=arruela_d);
    }
}
module torre_tampa(p) {
    translate([p[0],p[1],fundo-eps]) cylinder(h=altura-fundo+eps,d=coluna_tampa_d);
    if(p[0]==6) translate([-eps,p[1]-2,fundo-eps]) cube([6+eps,4,altura-fundo+eps]);
    translate([p[0]-2,p[1]<interno_y/2?-eps:p[1],fundo-eps])
        cube([4,p[1]<interno_y/2?p[1]+eps:interno_y-p[1]+eps,altura-fundo+eps]);
}
module olhal_cabo(p) { translate([p[0]-4,p[1]-2,fundo-eps]) difference() {
    cube([8,4,7+eps]);
    translate([2,-eps,2.5]) cube([4,4+2*eps,2]);
}}
// Extrusao em X com perfil definido no plano YZ.
module perfil_x(x,y,z,l) {
    multmatrix([[0,0,1,x],[1,0,0,y],[0,1,0,z],[0,0,0,1]]) linear_extrude(l) children();
}
module gota(d) { hull(){circle(d=d);translate([0,d/sqrt(2)-.02]) circle(r=.02,$fn=8);} }
function topo_apoio_shield(z)=z+(z<20?4.6:4.5);
module apoio_shield(y,z) {
    x=shield_x_traseira;
    b=topo_apoio_shield(z);
    // Contato apenas em torno do furo; escora inferior cresce ate a parede.
    hull() {
        perfil_x(x,y,z,eps) circle(d=5);
        translate([x+1.0,y-4.5,max(fundo-eps,z-3.55)]) cube([eps,9,b-max(fundo-eps,z-3.55)]);
    }
    hull() {
        translate([x+1.0-eps,y-4.5,max(fundo-eps,z-3.55)]) cube([2*eps,9,b-max(fundo-eps,z-3.55)]);
        translate([interno_x-eps,y-4.5,max(fundo-eps,z-8.6)]) cube([1.2,9,b-max(fundo-eps,z-8.6)]);
    }
}
module cortes_shield(y,z) {
    perfil_x(shield_x_traseira-eps,y,z,furo_shield_ate_x-shield_x_traseira+eps) gota(furo_m3);
    perfil_x(porca_shield_x,y,z,porca_m3_h)
        rotate(30) circle(r=porca_m3_AF/(2*cos(30)),$fn=6);
    translate([porca_shield_x,y-porca_m3_AF/2,z])
        cube([porca_m3_h,porca_m3_AF,topo_apoio_shield(z)-z+eps]);
}
module base() { centrado() difference() {
    union() {
        difference() {
            translate([-parede,-parede,0]) linear_extrude(altura) retangulo_arredondado(interno_x+2*parede,interno_y+2*parede,raio);
            translate([0,0,fundo]) linear_extrude(altura-fundo+eps) retangulo_arredondado(interno_x,interno_y,raio-parede);
        }
        for(p=apoios_placa) corpo_apoio(p);
        for(p=apoios_shield_yz) apoio_shield(p[0],p[1]);
        for(p=colunas_tampa) torre_tampa(p);
        olhal_cabo(olhal_pos);
    }
    for(p=apoios_placa) {
        translate([p[0],p[1],8.5]) cylinder(h=placa_z-8.5+eps,d=furo_m2);
        canal_porcas(p,porca_m2_AF,porca_m2_h,10,p[0]<interno_x/2?"x+":"x-");
    }
    for(p=apoios_shield_yz) cortes_shield(p[0],p[1]);
    for(p=colunas_tampa) {
        translate([p[0],p[1],31.5]) cylinder(h=altura-31.5+eps,d=furo_m3);
        canal_porcas(p,porca_m3_AF,porca_m3_h,porca_tampa_z,p[1]<interno_y/2?"y+":"y-",8);
    }
} }
module guia_tampa_2d() { difference() {
    translate([guia_folga,guia_folga]) retangulo_arredondado(interno_x-2*guia_folga,interno_y-2*guia_folga,raio-parede-guia_folga);
    translate([guia_folga+guia_t,guia_folga+guia_t]) retangulo_arredondado(interno_x-2*(guia_folga+guia_t),interno_y-2*(guia_folga+guia_t),max(.5,raio-parede-guia_folga-guia_t));
    for(p=colunas_tampa) {
        translate(p) circle(r=coluna_tampa_d/2+.65);
        translate([p[0]-2.7,p[1]<interno_y/2?-eps:interno_y-9]) square([5.4,9+2*eps]);
    }
    for(y=[0,interno_y-8.7]) translate([-eps,y-eps]) square([8.7+2*eps,8.7+2*eps]);
    for(y=[shield_y_inicio+shield_recuo,shield_y_fim-shield_recuo])
        translate([interno_x-4,y-5.2]) square([5,10.4]);
} }
module tampa_montada() { centrado() difference() {
    union() {
        translate([-parede,-parede,altura]) linear_extrude(tampa_t) retangulo_arredondado(interno_x+2*parede,interno_y+2*parede,raio);
        translate([0,0,altura-guia_h]) linear_extrude(guia_h+eps) guia_tampa_2d();
    }
    for(p=colunas_tampa) translate([p[0],p[1],altura-guia_h-eps]) cylinder(h=tampa_t+guia_h+2*eps,d=furo_m3);
} }
module tampa_impressao() { translate([0,0,altura+tampa_t]) rotate([180,0,0]) tampa_montada(); }

// A geometria local do shield usa u da USB-A para a outra extremidade;
// v da borda 5V para a borda 3V; w positivo para o lado da bateria.
module pose_shield() {
    multmatrix([[0,0,-1,shield_x_traseira],[-1,0,0,shield_y_fim],[0,1,0,shield_z_borda],[0,0,0,1]]) children();
}
module pcb_principal_local() { translate([placa_origem[0],placa_origem[1],placa_z]) difference() {
    cube([placa_x,placa_y,placa_t]);
    for(p=furos_placa) translate([p[0],p[1],-eps]) cylinder(h=placa_t+2*eps,d=furo_m2);
} }
module inferior_principal_local() { translate([placa_origem[0],placa_origem[1],placa_z-projecao_abaixo]) difference() {
    cube([placa_x,placa_y,projecao_abaixo]);
    for(p=furos_placa) translate([p[0],p[1],-eps]) cylinder(h=projecao_abaixo+2*eps,d=12.2);
} }
module superior_principal_local() { translate([placa_origem[0],placa_origem[1],placa_z+placa_t]) cube([placa_x,placa_y,projecao_acima]); }
module antena_local() { translate([antena_x,placa_origem[1]-antena_projecao,antena_z]) cube([antena_largura_ref,antena_projecao,.8]); }
module pcb_shield_local() { pose_shield() difference() {
    cube([shield_x,shield_y,shield_t]);
    for(p=furos_shield) translate([p[0],p[1],-eps]) cylinder(h=shield_t+2*eps,d=furo_m3);
} }
module bateria_envelope_local() { pose_shield() translate([16,3,shield_t]) cube([81,23,shield_altura_total-shield_t]); }
module bateria_visual_local() { pose_shield() {
    color([.19,.22,.26]) translate([16,3,shield_t]) cube([81,23,5]);
    color([.83,.45,.60]) translate([23,14.5,15.65]) rotate([0,90,0]) cylinder(h=68,d=18.6);
    for(u=[17,91]) color([.19,.22,.26]) translate([u,4,6.5]) cube([6,21,17.7]);
} }
module usb_shield_local() { pose_shield() translate([-usb_avanco,(shield_y-usb_largura_reservada)/2,shield_t]) cube([usb_avanco+8,usb_largura_reservada,9]); }
module usb_carga_ref_local() { pose_shield() translate([95,10,-4]) cube([6,9,4]); }
module chave_local() { pose_shield() translate([10,shield_y-3,shield_t]) cube([15,5,5]); }
module usb_esp_servico_local() { translate([usb_esp_centro_x-usb_plug_larg/2,usb_esp_face_y,usb_esp_z-usb_plug_alt/2]) cube([usb_plug_larg,usb_plug_comp,usb_plug_alt]); }
module caminho_fio(pontos) { for(i=[0:len(pontos)-2]) hull() {
    translate(pontos[i]) sphere(d=fio_d,$fn=16);
    translate(pontos[i+1]) sphere(d=fio_d,$fn=16);
} }
module fios_local() { for(i=[0:1]) color(i==0?[.81,.16,.21]:[.14,.18,.22]) {
    caminho_fio(cabos_shield[i]); caminho_fio(cabos_placa[i]);
} }
module conector_local() { translate(conector_origem) cube(conector_dim); }
module reserva_antena_local() { translate([antena_x,eps,6+eps]) cube([antena_largura_ref,folga_antena_parede-2*eps,altura-guia_h-6-2*eps]); }
module refs_principal() { union(){pcb_principal_local();inferior_principal_local();superior_principal_local();antena_local();} }
module refs_shield() { union(){pcb_shield_local();bateria_envelope_local();usb_shield_local();usb_carga_ref_local();chave_local();} }
module varredura_z(h=40) { hull(){children();translate([0,0,h]) children();} }
module retirada_shield_local() { translate([-4.25,0,0]) {
    varredura_z() pcb_shield_local();
    varredura_z() bateria_envelope_local();
    varredura_z() usb_shield_local();
    varredura_z() usb_carga_ref_local();
    varredura_z() chave_local();
} }
module refs_montagem() { union(){refs_principal();refs_shield();fios_local();conector_local();} }
module montagem(aberta=false,explodir=false) {
    color([.26,.47,.59]) base();
    translate([0,0,explodir?23:0]) centrado() {
        color([.14,.42,.37]) pcb_principal_local();
        color([.16,.23,.29,.27]) superior_principal_local();
        color([.12,.16,.21]) antena_local();
        color([.15,.20,.25]) pcb_shield_local();
        bateria_visual_local();
        color([.72,.75,.77]) {usb_shield_local();usb_carga_ref_local();}
        color([.18,.18,.21]) chave_local();
        if(mostrar_cabos) {fios_local();color([.81,.83,.84]) conector_local();}
        if(mostrar_reserva) color([.1,.7,.8,.24]) reserva_antena_local();
    }
    if(!aberta) color([.42,.61,.70]) translate([0,0,explodir?58:0]) tampa_montada();
}

// As pecas auxiliares abaixo sao preenchidas pelo gerador a partir da v0.9.
module arruela() {difference() {cylinder(h=arruela_t,d=arruela_d); translate([0,0,-eps]) cylinder(h=arruela_t+2*eps,d=furo_m2);}}
module gabarito_placa() {difference() {cube([80,60,1.2]);for(x=[2,78],y=[2,58]) translate([x,y,-eps]) cylinder(h=1.2+2*eps,d=furo_m2);}}
module arruela_shield() {difference() {cylinder(h=arruela_t,d=arruela_shield_d); translate([0,0,-eps]) cylinder(h=arruela_t+2*eps,d=furo_shield);}}
module gabarito_shield() {difference() {
    union() {cube([shield_x,shield_y,1.2]);translate([-usb_avanco,(shield_y-usb_largura_reservada)/2,0]) cube([usb_avanco+eps,usb_largura_reservada,1.2]);}
    for(p=furos_shield) translate([p[0],p[1],-eps]) cylinder(h=1.2+2*eps,d=furo_shield);
}}
module calibre_furos() {
    ds=[2.2,2.4,2.6,3.2,3.4,3.6];
    difference() {
        linear_extrude(6) retangulo_arredondado(76,22,2);
        for(i=[0:5]) {
            translate([8+i*12,14,-eps]) cylinder(h=6+2*eps,d=ds[i]);
            translate([8+i*12,4,5.4]) linear_extrude(0.6+eps) text(str(ds[i]),size=3,halign="center",font="DejaVu Sans");
        }
    }
}
module calibre_porcas() {difference() {
    linear_extrude(10) retangulo_arredondado(48,28,2);
    for(i=[0:1]) {
        p=[12+24*i,11]; AF=i==0?porca_m2_AF:porca_m3_AF; h=i==0?porca_m2_h:porca_m3_h; z=i==0?5.2:4.4;
        translate([p[0],p[1],3]) cylinder(h=7+eps,d=i==0?furo_m2:furo_m3);
        canal_porcas(p,AF,h,z,"y-",16);
        translate([p[0],21,9.4]) linear_extrude(0.6+eps) text(i==0?"M2 4.3":"M3 5.6",size=2.6,halign="center",font="DejaVu Sans");
    }
}}
module empurrador(tamanho=2) {
    w=tamanho==2?4:5.3; h=tamanho==2?1.4:2.2;
    union() {
        translate([0,-w/2,0]) cube([12,w,h]);
        translate([10,-6,0]) linear_extrude(4) retangulo_arredondado(28,12,2);
        translate([26,0,4-eps]) linear_extrude(0.4+eps) text(str(tamanho),size=5,halign="center",valign="center",font="DejaVu Sans");
    }
}
module cupom() { linear_extrude(6) retangulo_arredondado(40,30,2); }

if(parte=="base") base();
else if(parte=="tampa") tampa_impressao();
else if(parte=="aberta") montagem(true,false);
else if(parte=="montada") montagem();
else if(parte=="explodida") montagem(false,true);
else if(parte=="colisao_base") intersection(){base();centrado() {
    refs_principal();translate([-.01,0,0]) refs_shield();fios_local();conector_local();
}}
else if(parte=="colisao_tampa") intersection(){tampa_montada();centrado() refs_montagem();}
else if(parte=="colisao_fecho") intersection(){base();translate([0,0,.01]) tampa_montada();}
else if(parte=="colisao_pcbs") centrado() intersection(){refs_principal();refs_shield();}
else if(parte=="colisao_fios") centrado() intersection(){fios_local();union(){refs_principal();refs_shield();}}
else if(parte=="colisao_antena") intersection(){centrado() reserva_antena_local();union(){base();tampa_montada();centrado() refs_montagem();}}
else if(parte=="colisao_usb_servico") intersection(){centrado() usb_esp_servico_local();union(){base();centrado() refs_shield();}}
else if(parte=="colisao_retirada_shield") intersection(){base();centrado() retirada_shield_local();}
else if(parte=="colisao_acesso_m3") intersection(){base();centrado() for(p=apoios_shield_yz) perfil_x(85,p[0],p[1],shield_x_traseira-shield_t-arruela_t-85-eps) circle(d=6);}
else if(parte=="fundo_faltante") difference(){centrado() translate([-parede+.01,-parede+.01,.01]) linear_extrude(fundo-.02) retangulo_arredondado(interno_x+2*parede-.02,interno_y+2*parede-.02,raio-.01);base();}
else if(parte=="arruela") arruela();
else if(parte=="arruela_shield") arruela_shield();
else if(parte=="gabarito_placa") gabarito_placa();
else if(parte=="gabarito_shield") gabarito_shield();
else if(parte=="calibre_furos") calibre_furos();
else if(parte=="calibre_porcas") calibre_porcas();
else if(parte=="empurrador_m2") empurrador(2);
else if(parte=="empurrador_m3") empurrador(3);
else if(parte=="cupom_adesivo") cupom();
else assert(false,"Parte desconhecida");
